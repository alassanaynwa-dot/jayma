"""Formulaires d'authentification dashboard + client."""
from django import forms
from django.contrib.auth import authenticate

from .models import ClientAddress, phone_validator


class LoginForm(forms.Form):
    """Login par username ou email + mot de passe (merchants et admins)."""

    identifier = forms.CharField(
        label="Nom d'utilisateur ou email",
        widget=forms.TextInput(attrs={
            "class": "input",
            "placeholder": "ton-identifiant",
            "autofocus": "autofocus",
            "autocomplete": "username",
        }),
    )
    password = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={
            "class": "input",
            "placeholder": "••••••••",
            "autocomplete": "current-password",
        }),
    )

    def __init__(self, *args, request=None, **kwargs):
        self.request = request
        self.user = None
        super().__init__(*args, **kwargs)

    def clean(self):
        data = super().clean()
        identifier = data.get("identifier")
        password = data.get("password")
        if not identifier or not password:
            return data

        from django.contrib.auth import get_user_model
        User = get_user_model()
        username = identifier
        if "@" in identifier:
            found = User.objects.filter(email__iexact=identifier).first()
            if found:
                username = found.username

        user = authenticate(self.request, username=username, password=password)
        if user is None:
            raise forms.ValidationError("Identifiants incorrects.")
        if not user.is_active:
            raise forms.ValidationError("Ce compte est désactivé.")

        self.user = user
        return data


# ============ Client — auth OTP ============

class PhoneLoginForm(forms.Form):
    """Étape 1 : le client entre son numéro, on envoie un OTP par SMS."""
    phone = forms.CharField(
        label="Ton numéro de téléphone",
        widget=forms.TextInput(attrs={
            "class": "input text-lg font-mono",
            "placeholder": "+221 77 123 45 67",
            "autofocus": "autofocus",
            "autocomplete": "tel",
            "inputmode": "tel",
        }),
    )

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").replace(" ", "")
        phone_validator(phone)
        return phone


class OTPVerifyForm(forms.Form):
    """Étape 2 : le client tape le code reçu par SMS."""
    code = forms.CharField(
        label="Code reçu par SMS",
        max_length=4,
        min_length=4,
        widget=forms.TextInput(attrs={
            "class": "input text-center text-3xl font-mono tracking-[0.5em]",
            "placeholder": "••••",
            "autofocus": "autofocus",
            "autocomplete": "one-time-code",
            "inputmode": "numeric",
            "pattern": "[0-9]{4}",
        }),
    )

    def clean_code(self):
        code = (self.cleaned_data.get("code") or "").strip()
        if not code.isdigit() or len(code) != 4:
            raise forms.ValidationError("Le code doit faire 4 chiffres.")
        return code


class ClientAddressForm(forms.ModelForm):
    class Meta:
        model = ClientAddress
        fields = ["label", "address", "city", "is_default"]
        labels = {
            "label": "Libellé",
            "address": "Adresse complète",
            "city": "Ville",
            "is_default": "Adresse par défaut",
        }
        widgets = {
            "label":   forms.TextInput(attrs={
                "class": "input",
                "placeholder": "Maison, Bureau…",
                "autocapitalize": "words",
            }),
            "address": forms.Textarea(attrs={
                "class": "input",
                "rows": 2,
                "autocomplete": "street-address",
                "autocapitalize": "sentences",
            }),
            "city":    forms.TextInput(attrs={
                "class": "input",
                "autocomplete": "address-level2",
                "autocapitalize": "words",
            }),
        }
