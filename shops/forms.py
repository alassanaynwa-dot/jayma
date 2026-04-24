"""Formulaires shops — côté dashboard commerçant."""
from django import forms

from .models import Shop


class ShopSettingsForm(forms.ModelForm):
    """Paramètres modifiables par le commerçant depuis son dashboard."""

    class Meta:
        model = Shop
        # Note : slug et commission_rate NON modifiables par le commerçant
        # (slug → identité boutique ; commission → admin Jappesi uniquement).
        fields = [
            "name", "description",
            "logo", "banner",
            "phone", "whatsapp", "email",
            "city", "address",
            "theme_color",
            "is_active",
        ]
        labels = {
            "name": "Nom de la boutique",
            "description": "Description",
            "logo": "Logo (carré, max 1 Mo)",
            "banner": "Bannière (format paysage, max 2 Mo)",
            "phone": "Téléphone affiché",
            "whatsapp": "Numéro WhatsApp",
            "email": "Email de contact",
            "city": "Ville",
            "address": "Adresse complète",
            "theme_color": "Couleur principale",
            "is_active": "Boutique ouverte",
        }
        help_texts = {
            "is_active": "Décoche pour fermer temporairement (une page 'boutique fermée' s'affichera).",
            "theme_color": "Format hexadécimal (ex : #C45C2A).",
            "whatsapp": "Format international, ex : +221 77 123 45 67.",
        }
        widgets = {
            "name":        forms.TextInput(attrs={"class": "input"}),
            "description": forms.Textarea(attrs={"class": "input", "rows": 4}),
            "phone":       forms.TextInput(attrs={"class": "input", "placeholder": "+221 77 123 45 67"}),
            "whatsapp":    forms.TextInput(attrs={"class": "input", "placeholder": "+221 77 123 45 67"}),
            "email":       forms.EmailInput(attrs={"class": "input"}),
            "city":        forms.TextInput(attrs={"class": "input"}),
            "address":     forms.Textarea(attrs={"class": "input", "rows": 2}),
            "theme_color": forms.TextInput(attrs={
                "class": "input font-mono", "type": "color",
                "style": "height: 42px;",
            }),
        }
