from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.decorators import action

from core.tasks import send_merchant_welcome

from .models import Shop, ShopRequest
from .services.approval import ApprovalError, approve_shop_request


@admin.register(Shop)
class ShopAdmin(ModelAdmin):
    list_display = ("name", "slug", "owner", "city", "is_approved", "is_active", "commission_rate", "created_at")
    list_filter = ("is_approved", "is_active", "city")
    search_fields = ("name", "slug", "owner__username", "owner__email", "phone")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("owner",)


@admin.register(ShopRequest)
class ShopRequestAdmin(ModelAdmin):
    list_display = ("shop_name", "desired_slug", "full_name", "email",
                    "city", "status", "created_at")
    list_filter = ("status", "city")
    search_fields = ("shop_name", "desired_slug", "email", "phone", "full_name")
    readonly_fields = ("created_at", "reviewed_at", "reviewed_by")
    ordering = ("-created_at",)

    actions_detail = ["approve_request", "reject_request"]
    actions_list = ["approve_selected"]

    # --- Actions détail (boutons sur la page d'une demande) ---

    @action(description=_("Approuver cette demande et créer la boutique"))
    def approve_request(self, request, object_id):
        shop_request = ShopRequest.objects.get(pk=object_id)
        try:
            shop, temp_password = approve_shop_request(shop_request, reviewed_by=request.user)
        except ApprovalError as exc:
            self.message_user(request, f"Refus : {exc}", level=messages.ERROR)
            return

        # Notification asynchrone
        try:
            send_merchant_welcome.delay(shop.pk, temp_password)
        except Exception:
            send_merchant_welcome(shop.pk, temp_password)

        self.message_user(
            request,
            f"Boutique '{shop.name}' créée sur {shop.slug}.jayma.sn. Email + SMS envoyés au commerçant.",
            level=messages.SUCCESS,
        )

    @action(description=_("Rejeter cette demande"))
    def reject_request(self, request, object_id):
        from django.utils import timezone
        shop_request = ShopRequest.objects.get(pk=object_id)
        if shop_request.status == ShopRequest.Status.REJECTED:
            self.message_user(request, "Déjà rejetée.", level=messages.WARNING)
            return
        shop_request.status = ShopRequest.Status.REJECTED
        shop_request.reviewed_by = request.user
        shop_request.reviewed_at = timezone.now()
        shop_request.save()
        self.message_user(request, "Demande rejetée.", level=messages.INFO)

    # --- Action liste (pour approbation en masse) ---

    @action(description=_("Approuver les demandes sélectionnées"))
    def approve_selected(self, request, queryset):
        ok = 0
        failed = 0
        for sr in queryset.filter(status=ShopRequest.Status.PENDING):
            try:
                shop, temp_password = approve_shop_request(sr, reviewed_by=request.user)
                try:
                    send_merchant_welcome.delay(shop.pk, temp_password)
                except Exception:
                    send_merchant_welcome(shop.pk, temp_password)
                ok += 1
            except ApprovalError:
                failed += 1
        self.message_user(
            request,
            f"{ok} demande(s) approuvée(s), {failed} en erreur.",
            level=messages.SUCCESS if failed == 0 else messages.WARNING,
        )
