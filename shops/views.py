"""Vues shops — boutique publique + paramètres dashboard."""
from django.contrib import messages
from django.core.cache import cache
from django.db import IntegrityError, models, transaction
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from accounts.decorators import merchant_required

from .forms import ShopSettingsForm
from .models import WaitlistSignup

# ============ PUBLIC ============

# 200 req/h par IP : protège contre un scraping en masse des homes boutiques.
# Un visiteur normal qui rafraîchit ne sera jamais bloqué. Les crawlers legit
# (Google, Bing) qui crawlent peuvent être whitelisted plus tard côté Nginx.
@ratelimit(key="ip", rate="200/h", method="GET", block=True)
def shop_public_home(request):
    if not request.shop:
        raise Http404("Aucune boutique détectée sur ce sous-domaine.")

    shop = request.shop

    # Boutique sans aucun produit actif → page "en préparation" avec form
    # waitlist au lieu d'une boutique vide. Évite que le visiteur tombe sur
    # une coquille vide quand le commerçant a partagé son lien trop tôt.
    if not shop.products.filter(is_active=True).exists():
        signup_count = shop.waitlist_signups.count()
        return render(request, "shops/public_coming_soon.html", {
            "shop": shop,
            "signup_count": signup_count,
            "submitted": request.GET.get("merci") == "1",
        })

    featured = (
        shop.products.with_ratings()
        .filter(is_active=True, is_featured=True)
        .prefetch_related("images")[:8]
    )
    latest = (
        shop.products.with_ratings()
        .filter(is_active=True)
        .prefetch_related("images")[:8]
    )

    # Catégories : on n'affiche QUE les univers (racines) avec un compteur
    # qui inclut les produits du parent + de ses sous-catégories. On masque
    # les univers vides (0 produit) pour ne pas encombrer la home.
    #
    # Optimisation : on compte les produits actifs pour TOUTES les categories
    # de la boutique en 1 seule query GROUP BY, puis on agrège côté Python
    # parent + enfants. Évite le N+1 (1 SELECT COUNT par univers).
    cat_counts = dict(
        shop.products.filter(is_active=True, category__isnull=False)
        .values("category_id")
        .annotate(c=models.Count("id"))
        .values_list("category_id", "c")
    )
    roots = list(
        shop.categories.filter(parent__isnull=True, is_active=True)
        .order_by("position", "name")
        .prefetch_related("children")
    )
    for root in roots:
        children_ids = [c.pk for c in root.children.all() if c.is_active]
        root.products_count = (
            cat_counts.get(root.pk, 0)
            + sum(cat_counts.get(cid, 0) for cid in children_ids)
        )
    categories = [r for r in roots if r.products_count > 0]

    # Bannière promo : premier coupon actif + dans les dates + quota non atteint
    now = timezone.now()
    promo_banner = (
        shop.coupons
        .filter(is_active=True, valid_from__lte=now)
        .filter(models.Q(valid_until__isnull=True) | models.Q(valid_until__gte=now))
        .order_by("valid_from")
        .first()
    )
    if promo_banner and promo_banner.max_uses is not None and promo_banner.uses_count >= promo_banner.max_uses:
        promo_banner = None

    return render(request, "shops/public_home.html", {
        "shop": shop, "featured": featured, "latest": latest, "categories": categories,
        "promo_banner": promo_banner,
    })


@require_POST
def shop_waitlist_register(request):
    """Inscription d'un visiteur à la waitlist d'une boutique en préparation.

    Crée un WaitlistSignup (ou retourne silencieusement si déjà inscrit pour
    le même couple shop+phone), envoie un SMS au commerçant pour le prévenir
    qu'un client potentiel attend l'ouverture, et redirige vers la home avec
    un flag ?merci=1 pour afficher le message de confirmation.
    """
    if not request.shop:
        raise Http404("Aucune boutique détectée sur ce sous-domaine.")

    from accounts.models import normalize_phone_sn

    shop = request.shop
    raw_phone = (request.POST.get("phone") or "").strip()
    name = (request.POST.get("name") or "").strip()[:100]
    email = (request.POST.get("email") or "").strip()[:254]

    # Validation phone — obligatoire
    try:
        phone = normalize_phone_sn(raw_phone)
    except Exception:
        messages.error(
            request,
            "Numéro de téléphone invalide. Format attendu : 77 123 45 67 ou +221771234567.",
        )
        return redirect("shops_public:home")

    # Création (ou silencieux si déjà inscrit). On wrap dans un savepoint
    # transaction.atomic() pour que l'IntegrityError du UniqueConstraint ne
    # casse pas la transaction parente (sinon impossible de continuer en
    # tests + side-effects).
    try:
        with transaction.atomic():
            signup = WaitlistSignup.objects.create(
                shop=shop, name=name, phone=phone, email=email,
            )
    except IntegrityError:
        # Déjà inscrit avec ce numéro pour cette boutique : on traite comme
        # un succès silencieux (pas de double notif au commerçant).
        signup = None

    # Notif SMS au commerçant — best-effort, n'échoue pas le flow
    if signup is not None and shop.owner and shop.owner.phone:
        try:
            from notifications.services.sms import send_sms
            who = name or "Quelqu'un"
            text = (
                f"{who} ({phone}) attend l'ouverture de ta boutique "
                f"{shop.name} sur Jappesi. Total liste d'attente : "
                f"{shop.waitlist_signups.count()}. Ajoute tes premiers "
                f"produits pour leur répondre !"
            )
            send_sms(shop.owner.phone, text)
        except Exception:
            pass

    return redirect(f"{request.path}?merci=1")


# ============ DASHBOARD ============

@merchant_required
def shop_settings(request):
    shop = request.merchant_shop
    if request.method == "POST":
        form = ShopSettingsForm(request.POST, request.FILES, instance=shop)
        if form.is_valid():
            form.save()
            cache.delete(f"shop:slug:{shop.slug}")
            messages.success(request, "Paramètres de ta boutique enregistrés.")
            return redirect("shops_dashboard:settings")
    else:
        form = ShopSettingsForm(instance=shop)
    return render(request, "dashboard/shop/settings.html", {
        "shop": shop, "form": form,
    })


@merchant_required
def shop_waitlist_dashboard(request):
    """Page dashboard : liste des inscrits à la waitlist du commerçant.

    Permet au commerçant de voir qui attend l'ouverture de sa boutique.
    Quand il aura mis ses premiers produits, il pourra contacter ces
    personnes (par WhatsApp directement via les liens, ou plus tard avec
    une fonction "Notifier toute la waitlist" en bulk SMS).
    """
    shop = request.merchant_shop
    signups = shop.waitlist_signups.order_by("-created_at")
    has_products = shop.products.filter(is_active=True).exists()
    return render(request, "dashboard/shop/waitlist.html", {
        "shop": shop,
        "signups": signups,
        "signup_count": signups.count(),
        "has_products": has_products,
    })
