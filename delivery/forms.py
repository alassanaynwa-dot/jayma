"""Formulaires gestion des livreurs + zones."""
from django import forms

from .models import Courier, DeliveryZone, phone_validator


class DeliveryZoneForm(forms.ModelForm):
    class Meta:
        model = DeliveryZone
        fields = ["name", "cities", "fee_xof", "position", "is_active"]
        labels = {
            "name": "Nom de la zone",
            "cities": "Villes / quartiers couverts",
            "fee_xof": "Prix de livraison (XOF)",
            "position": "Ordre d'affichage",
            "is_active": "Zone active",
        }
        help_texts = {
            "cities": "Séparés par des virgules. Ex : Plateau, Médina, Point E",
            "fee_xof": "Montant en XOF entier. Mets 0 pour une zone gratuite.",
        }
        widgets = {
            "name":     forms.TextInput(attrs={"class": "input", "placeholder": "Dakar centre"}),
            "cities":   forms.Textarea(attrs={"class": "input", "rows": 2, "placeholder": "Plateau, Médina, Fann, Point E"}),
            "fee_xof":  forms.NumberInput(attrs={"class": "input", "min": 0, "step": 500}),
            "position": forms.NumberInput(attrs={"class": "input", "min": 0}),
        }

    def __init__(self, *args, shop=None, **kwargs):
        self.shop = shop
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        z = super().save(commit=False)
        if self.shop:
            z.shop = self.shop
        if commit:
            z.save()
        return z


class CourierForm(forms.ModelForm):
    class Meta:
        model = Courier
        fields = ["name", "phone", "vehicle", "covered_zones", "zones", "notes", "is_active"]
        labels = {
            "name": "Nom du livreur",
            "phone": "Téléphone",
            "vehicle": "Moyen de transport",
            "covered_zones": "Zones tarifées couvertes",
            "zones": "Quartiers (notes libres)",
            "notes": "Notes",
            "is_active": "Livreur actif",
        }
        help_texts = {
            "covered_zones": "Sélectionne les zones tarifées où ce livreur peut intervenir.",
        }
        widgets = {
            "name":    forms.TextInput(attrs={"class": "input", "placeholder": "Ex : Modou Fall"}),
            "phone":   forms.TextInput(attrs={"class": "input", "placeholder": "+221 77 123 45 67"}),
            "vehicle": forms.Select(attrs={"class": "input"}),
            "zones":   forms.TextInput(attrs={"class": "input", "placeholder": "Plateau, Médina…"}),
            "notes":   forms.Textarea(attrs={"class": "input", "rows": 2}),
            "covered_zones": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, shop=None, **kwargs):
        self.shop = shop
        super().__init__(*args, **kwargs)
        if shop:
            self.fields["covered_zones"].queryset = shop.delivery_zones.filter(is_active=True)

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").replace(" ", "")
        phone_validator(phone)
        return phone

    def save(self, commit=True):
        c = super().save(commit=False)
        if self.shop:
            c.shop = self.shop
        if commit:
            c.save()
            self.save_m2m()
        return c
