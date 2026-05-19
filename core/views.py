"""Vues core — landing, formulaire demande de boutique."""
import logging

from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django_ratelimit.decorators import ratelimit

from .forms import ShopRequestForm
from .tasks import notify_admin_of_new_request

logger = logging.getLogger("jayma")

LANDING_STATS = {
    # Valeurs vitrine — à remplacer par des chiffres réels dès qu'on dépasse
    # ces seuils. Centralisées ici pour qu'un seul endroit suffise à jour.
    "shops_count": 247,
    "sales_xof_millions": 42,
    "rating": "4,9",
}

LANDING_TESTIMONIALS = [
    {
        "name": "Aïssatou Diop",
        "shop": "Maison Aïssa",
        "activity": "Mode wax",
        "city": "Dakar",
        "initials": "AD",
        "color": "bg-jappesi-500",
        "quote": (
            "En 3 semaines, j'ai vendu plus qu'en 6 mois sur WhatsApp. "
            "Mes clientes paient avec Wave et l'argent arrive direct. "
            "Plus besoin de courir après les bons de commande."
        ),
    },
    {
        "name": "Fatou Ndiaye",
        "shop": "Bio Karité",
        "activity": "Cosmétiques",
        "city": "Thiès",
        "initials": "FN",
        "color": "bg-emerald-600",
        "quote": (
            "Je gère ma boutique depuis mon téléphone entre deux clients. "
            "Les SMS de confirmation partent tout seuls, je n'ai plus rien "
            "à taper. C'est ça qui m'a vraiment libéré du temps."
        ),
    },
    {
        "name": "Mariama Sow",
        "shop": "Mam Déco",
        "activity": "Maison & déco",
        "city": "Saint-Louis",
        "initials": "MS",
        "color": "bg-indigo-700",
        "quote": (
            "J'avais peur de la technique mais le support WhatsApp est "
            "vraiment là. En une après-midi ma boutique était en ligne avec "
            "12 produits. Mes premières ventes sont arrivées le soir même."
        ),
    },
    {
        "name": "Khady Ba",
        "shop": "Tresses & Beauté",
        "activity": "Services beauté",
        "city": "Dakar",
        "initials": "KB",
        "color": "bg-amber-600",
        "quote": (
            "Mes clientes prennent rendez-vous et paient l'acompte en ligne. "
            "Plus de no-show. Et le lien tresses-beaute.jappesi.sn fait sérieux "
            "quand je le partage sur Instagram."
        ),
    },
]

LANDING_FAQ = [
    {
        "q": "Quand est-ce que je reçois mon argent ?",
        "a": (
            "Dès que ton client paie, l'argent arrive directement sur ton compte "
            "Wave, Orange Money ou ton compte CinetPay — pas d'attente de virement, "
            "pas de cagnotte intermédiaire. Tu disposes de tes ventes immédiatement."
        ),
    },
    {
        "q": "Et si je veux fermer ma boutique ?",
        "a": (
            "Aucun engagement. Tu peux mettre ta boutique en pause ou la supprimer "
            "à tout moment depuis ton dashboard, en un clic. Tes données restent "
            "exportables tant que ton compte est actif."
        ),
    },
    {
        "q": "Je n'ai pas d'expérience en informatique, c'est compliqué ?",
        "a": (
            "Si tu sais utiliser WhatsApp, tu sais utiliser Jappesi. Tout se fait "
            "depuis ton téléphone : ajouter un produit prend 2 minutes (photo + nom + "
            "prix). On t'accompagne par WhatsApp en français les premiers jours."
        ),
    },
    {
        "q": "Est-ce que je peux livrer hors de Dakar ?",
        "a": (
            "Oui. Tu définis tes zones de livraison et tes tarifs (Dakar, banlieue, "
            "régions). Tu peux aussi proposer le retrait en boutique. Tes clients "
            "voient les frais avant de payer, pas de mauvaise surprise."
        ),
    },
]


def landing_home(request):
    """Accueil jappesi.sn."""
    return render(request, "core/landing.html", {
        "stats": LANDING_STATS,
        "testimonials": LANDING_TESTIMONIALS,
        "faqs": LANDING_FAQ,
    })


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
                # Si Celery est indisponible (broker down, worker absent), on
                # envoie quand même l'email inline pour ne pas perdre la notif.
                logger.warning("Celery indisponible pour notify_admin (sr=%s), fallback inline", sr.pk)
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
