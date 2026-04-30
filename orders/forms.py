"""Formulaire checkout client."""
from django import forms

from accounts.models import phone_validator

from .models import Order


class CheckoutForm(forms.Form):
    client_name = forms.CharField(
        label="Nom complet",
        max_length=100,
        widget=forms.TextInput(attrs={
            "class": "input",
            "placeholder": "Ton nom",
            "autocomplete": "name",
            "autocapitalize": "words",
        }),
    )
    client_phone = forms.CharField(
        label="Téléphone",
        max_length=20,
        widget=forms.TextInput(attrs={
            "class": "input",
            "placeholder": "+221 77 123 45 67",
            "type": "tel",
            "inputmode": "tel",
            "autocomplete": "tel",
        }),
    )
    client_email = forms.EmailField(
        label="Email (optionnel)",
        required=False,
        widget=forms.EmailInput(attrs={
            "class": "input",
            "placeholder": "email@exemple.sn",
            "inputmode": "email",
            "autocomplete": "email",
            "autocapitalize": "off",
            "spellcheck": "false",
        }),
    )
    client_address = forms.CharField(
        label="Adresse de livraison",
        widget=forms.Textarea(attrs={
            "class": "input",
            "rows": 2,
            "placeholder": "Quartier, rue, repère…",
            "autocomplete": "street-address",
            "autocapitalize": "sentences",
        }),
    )
    client_city = forms.CharField(
        label="Ville",
        max_length=100,
        widget=forms.TextInput(attrs={
            "class": "input",
            "placeholder": "Dakar",
            "autocomplete": "address-level2",
            "autocapitalize": "words",
        }),
    )
    client_notes = forms.CharField(
        label="Notes (optionnel)",
        required=False,
        widget=forms.Textarea(attrs={
            "class": "input",
            "rows": 2,
            "placeholder": "Instructions de livraison…",
            "autocapitalize": "sentences",
        }),
    )
    payment_method = forms.ChoiceField(
        label="Mode de paiement",
        choices=Order.PaymentMethod.choices,
        widget=forms.RadioSelect,
    )

    def clean_client_phone(self):
        phone = (self.cleaned_data.get("client_phone") or "").replace(" ", "")
        phone_validator(phone)
        return phone
