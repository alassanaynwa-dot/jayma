"""Vues core — landing, formulaire demande de boutique."""
from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django_ratelimit.decorators import ratelimit

from .forms import ShopRequestForm
from .tasks import notify_admin_of_new_request


def landing_home(request):
    """Accueil jappesi.sn."""
    return render(request, "core/landing.html")


@ratelimit(key="ip", rate="5/h", method="POST", block=True)
def shop_request(request):
    """Formulaire de demande de création de boutique.

    Rate-limit anti-spam : 5 demandes/heure par IP suffisent largement pour
    un usage légitime (un commerçant ne soumet qu'une fois). Au-delà = bot.
    """
    if request.method == "POST":
        form = ShopRequestForm(request.POST)
        if form.is_valid():
            sr = form.save()
            # Notification admin en asynchrone (ne bloque pas la réponse)
            try:
                notify_admin_of_new_request.delay(sr.pk)
            except Exception:
                # Si Celery est indisponible, on envoie quand même l'email
                # inline pour ne pas perdre la notif en dev.
                notify_admin_of_new_request(sr.pk)

            messages.success(request, "Ta demande a bien été reçue !")
            return redirect(reverse("core:shop_request_confirmation") + f"?ref={sr.pk}")
    else:
        form = ShopRequestForm()

    return render(request, "core/shop_request.html", {"form": form})


def shop_request_confirmation(request):
    """Page de confirmation après soumission."""
    return render(request, "core/shop_request_confirmation.html")


def legal_cgu(request):
    return render(request, "core/legal/cgu.html")


def legal_cgv(request):
    return render(request, "core/legal/cgv.html")


def legal_mentions(request):
    return render(request, "core/legal/mentions.html")


def legal_confidentialite(request):
    return render(request, "core/legal/confidentialite.html")
