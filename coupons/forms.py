"""Formulaires côté commerçant pour gérer les codes promo."""
from django import forms

from .models import Coupon


class CouponForm(forms.ModelForm):
    class Meta:
        model = Coupon
        fields = [
            "code", "type", "value",
            "min_order_xof", "max_uses", "one_per_customer",
            "valid_from", "valid_until", "is_active",
        ]
        labels = {
            "code": "Code (ce que le client tape)",
            "type": "Type de remise",
            "value": "Valeur",
            "min_order_xof": "Panier minimum (XOF)",
            "max_uses": "Nombre max d'utilisations",
            "one_per_customer": "1 seule utilisation par client",
            "valid_from": "Valable à partir de",
            "valid_until": "Valable jusqu'à",
            "is_active": "Code actif",
        }
        help_texts = {
            "value": "Pour pourcentage : 10 = -10%. Pour montant : 500 = -500 XOF.",
        }
        widgets = {
            "code":         forms.TextInput(attrs={"class": "input uppercase font-mono", "placeholder": "SOLDES10"}),
            "type":         forms.Select(attrs={"class": "input"}),
            "value":        forms.NumberInput(attrs={"class": "input", "min": 0}),
            "min_order_xof":forms.NumberInput(attrs={"class": "input", "min": 0, "step": 500}),
            "max_uses":     forms.NumberInput(attrs={"class": "input", "min": 1}),
            "valid_from":   forms.DateTimeInput(attrs={"class": "input", "type": "datetime-local"}),
            "valid_until":  forms.DateTimeInput(attrs={"class": "input", "type": "datetime-local"}),
        }

    def __init__(self, *args, shop=None, **kwargs):
        self.shop = shop
        super().__init__(*args, **kwargs)
        # Format datetime-local attendu
        for f in ("valid_from", "valid_until"):
            if self.fields[f].widget.attrs.get("type") == "datetime-local":
                self.fields[f].input_formats = ["%Y-%m-%dT%H:%M"]

    def clean_code(self):
        code = (self.cleaned_data.get("code") or "").upper().strip()
        if not code:
            raise forms.ValidationError("Code obligatoire.")
        # Unicité par boutique (exclut self)
        qs = Coupon.objects.filter(shop=self.shop, code=code)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(f"Un code « {code} » existe déjà dans ta boutique.")
        return code

    def save(self, commit=True):
        c = super().save(commit=False)
        if self.shop:
            c.shop = self.shop
        if commit:
            c.save()
        return c
