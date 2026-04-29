"""
Vues compte client (côté boutique publique <slug>.jappesi.sn).

Auth par OTP SMS — pas de mot de passe, le client tape son téléphone,
reçoit un code à 4 chiffres, le saisit, est connecté. Compte créé au
premier usage.
"""
from functools import wraps

from django.contrib import messages
from django.contrib.auth import login, logout
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from orders.models import Order

from .forms import ClientAddressForm, OTPVerifyForm, PhoneLoginForm
from .models import ClientAddress
from .services.otp import send_otp, verify_otp

# Clé de session pour stocker le phone entre étape 1 et 2
OTP_PHONE_SESSION_KEY = "client_otp_phone"


def client_required(view_func):
    """Exige un user connecté avec role=client."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("client:login")
        if not request.user.is_client:
            return redirect("client:login")
        return view_func(request, *args, **kwargs)
    return wrapper


# ============ Auth OTP ============

@ratelimit(key="ip", rate="10/m", method="POST", block=True)
@ratelimit(key="post:phone", rate="3/m", method="POST", block=True)
def client_login(request):
    """Étape 1 : le client entre son numéro.

    Rate-limit serré : un OTP coûte un SMS (~10 FCFA). Sans limite, un attaquant
    peut épuiser le crédit AfricasTalking en quelques secondes.
    """
    if not request.shop:
        raise Http404()
    if request.user.is_authenticated and request.user.is_client:
        return redirect("client:home")

    if request.method == "POST":
        form = PhoneLoginForm(request.POST)
        if form.is_valid():
            phone = form.cleaned_data["phone"]
            result = send_otp(phone)
            if result.ok:
                request.session[OTP_PHONE_SESSION_KEY] = phone
                return redirect("client:verify_otp")
            form.add_error(None, result.error or "Erreur lors de l'envoi du code.")
    else:
        form = PhoneLoginForm()

    return render(request, "client/login.html", {"shop": request.shop, "form": form})


@ratelimit(key="ip", rate="20/m", method="POST", block=True)
@ratelimit(key="post:code", rate="10/m", method="POST", block=True)
def client_verify_otp(request):
    """Étape 2 : le client tape le code reçu.

    Limite plus permissive que client_login : pas de coût SMS. Mais on bloque
    quand même les bots qui essaient toutes les combinaisons à 4 chiffres.
    """
    if not request.shop:
        raise Http404()
    phone = request.session.get(OTP_PHONE_SESSION_KEY)
    if not phone:
        messages.info(request, "Entre d'abord ton numéro de téléphone.")
        return redirect("client:login")

    if request.method == "POST":
        form = OTPVerifyForm(request.POST)
        if form.is_valid():
            result = verify_otp(phone, form.cleaned_data["code"])
            if result.ok:
                login(request, result.user)
                request.session.pop(OTP_PHONE_SESSION_KEY, None)
                messages.success(request, "Bienvenue !")
                return redirect("client:home")
            form.add_error(None, result.error or "Code invalide.")
    else:
        form = OTPVerifyForm()

    # Masquage du phone pour affichage (+221 ** ** ** 67)
    masked = phone[:4] + " **" + " **" * ((len(phone) - 6) // 2) + " " + phone[-2:]
    return render(request, "client/verify_otp.html", {
        "shop": request.shop, "form": form, "phone": phone, "masked": masked,
    })


@require_POST
def client_resend_otp(request):
    if not request.shop:
        raise Http404()
    phone = request.session.get(OTP_PHONE_SESSION_KEY)
    if not phone:
        return redirect("client:login")
    result = send_otp(phone)
    if result.ok:
        messages.success(request, "Nouveau code envoyé.")
    else:
        messages.error(request, result.error or "Erreur.")
    return redirect("client:verify_otp")


def client_logout(request):
    logout(request)
    messages.info(request, "À bientôt !")
    return redirect("shops_public:home")


# ============ Espace client ============

@client_required
def client_home(request):
    """Page d'accueil compte client : stats + dernières commandes sur CETTE boutique."""
    shop = request.shop
    orders = (
        Order.objects.filter(shop=shop, client_phone=request.user.phone)
        .order_by("-created_at")[:10]
    )
    addresses = request.user.addresses.all()[:5]
    total_spent = sum(o.total_xof for o in Order.objects.filter(
        shop=shop, client_phone=request.user.phone
    ))
    return render(request, "client/home.html", {
        "shop": shop,
        "orders": orders,
        "addresses": addresses,
        "total_spent": total_spent,
        "orders_count": Order.objects.filter(shop=shop, client_phone=request.user.phone).count(),
    })


@client_required
def client_addresses(request):
    return render(request, "client/addresses.html", {
        "shop": request.shop,
        "addresses": request.user.addresses.all(),
    })


@client_required
def address_create(request):
    if request.method == "POST":
        form = ClientAddressForm(request.POST)
        if form.is_valid():
            addr = form.save(commit=False)
            addr.user = request.user
            addr.save()
            messages.success(request, "Adresse ajoutée.")
            return redirect("client:addresses")
    else:
        form = ClientAddressForm()
    return render(request, "client/address_form.html", {
        "shop": request.shop, "form": form, "address": None,
    })


@client_required
def address_edit(request, pk):
    addr = get_object_or_404(ClientAddress, pk=pk, user=request.user)
    if request.method == "POST":
        form = ClientAddressForm(request.POST, instance=addr)
        if form.is_valid():
            form.save()
            messages.success(request, "Adresse mise à jour.")
            return redirect("client:addresses")
    else:
        form = ClientAddressForm(instance=addr)
    return render(request, "client/address_form.html", {
        "shop": request.shop, "form": form, "address": addr,
    })


@client_required
@require_POST
def address_delete(request, pk):
    addr = get_object_or_404(ClientAddress, pk=pk, user=request.user)
    addr.delete()
    messages.success(request, "Adresse supprimée.")
    return redirect("client:addresses")
