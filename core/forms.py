"""Formulaires publics jappesi.sn."""
from django import forms
from django.core.exceptions import ValidationError
from django.utils.text import slugify

from accounts.models import phone_validator
from config.middleware import RESERVED_SUBDOMAINS
from shops.models import Shop, ShopRequest


class ShopRequestForm(forms.ModelForm):
    """Formulaire de demande de création d'une boutique."""

    # Override explicite : on accepte TOUT en entrée (accents, espaces, majuscules)
    # et on normalise dans clean_desired_slug(). Ça évite que les validators
    # stricts du SlugField du model bloquent avant notre normalisation.
    desired_slug = forms.CharField(
        max_length=80,
        required=True,
        label="Adresse en ligne",
        widget=forms.TextInput(attrs={
            "class": "input",
            "placeholder": "Chez Awa, 62 rue du commerce…",
            "id": "id_desired_slug",
        }),
    )

    # On rajoute une case à cocher pour l'acceptation des conditions
    terms_accepted = forms.BooleanField(
        required=True,
        label="J'accepte les conditions de Jappesi (commission 8%).",
    )

    class Meta:
        model = ShopRequest
        fields = [
            "full_name", "email", "phone", "city",
            "shop_name", "desired_slug",
            "product_category", "description",
        ]
        labels = {
            "full_name": "Ton nom complet",
            "email": "Email",
            "phone": "Téléphone (Sénégal)",
            "city": "Ville",
            "shop_name": "Nom de ta boutique",
            "desired_slug": "Adresse en ligne",
            "product_category": "Que vends-tu ?",
            "description": "Décris ta boutique (optionnel)",
        }
        help_texts = {
            "desired_slug": "Tape ce que tu veux — accents, espaces, majuscules autorisés. On normalise automatiquement.",
            "phone": "Format : +221 77 123 45 67",
            "product_category": "Ex : vêtements, cosmétiques, électronique...",
        }
        widgets = {
            "full_name":        forms.TextInput(attrs={"class": "input", "placeholder": "Awa Diop"}),
            "email":            forms.EmailInput(attrs={"class": "input", "placeholder": "awa@exemple.sn"}),
            "phone":            forms.TextInput(attrs={"class": "input", "placeholder": "+221 77 123 45 67"}),
            "city":             forms.TextInput(attrs={"class": "input", "placeholder": "Dakar"}),
            "shop_name":        forms.TextInput(attrs={"class": "input", "placeholder": "Chez Awa"}),
            "product_category": forms.TextInput(attrs={"class": "input", "placeholder": "Vêtements"}),
            "description":      forms.Textarea(attrs={"class": "input", "rows": 3, "placeholder": "Optionnel"}),
        }

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").replace(" ", "")
        phone_validator(phone)
        return phone

    def clean_desired_slug(self):
        """
        On accepte TOUT ce que le user tape (accents, espaces, majuscules,
        chiffres) et on normalise automatiquement via slugify().
        """
        raw = (self.cleaned_data.get("desired_slug") or "").strip()
        if not raw:
            raise ValidationError("Choisis une adresse pour ta boutique.")

        slug = slugify(raw)  # "62 rue du commerce" → "62-rue-du-commerce"
        if not slug:
            raise ValidationError(
                "Impossible de normaliser cette adresse. Utilise des lettres ou des chiffres."
            )
        # Le slug doit faire au moins 3 caractères et max 40
        if len(slug) < 3:
            raise ValidationError("L'adresse doit faire au moins 3 caractères.")
        if len(slug) > 40:
            slug = slug[:40].rstrip("-")

        if slug in RESERVED_SUBDOMAINS:
            raise ValidationError(
                f"L'adresse « {slug} » est réservée par Jappesi. Choisis-en une autre."
            )

        if Shop.objects.filter(slug=slug).exists():
            raise ValidationError(
                f"L'adresse « {slug} » est déjà prise. Choisis-en une autre."
            )

        if ShopRequest.objects.filter(
            desired_slug=slug, status=ShopRequest.Status.PENDING
        ).exists():
            raise ValidationError(
                f"Une demande pour « {slug} » est déjà en cours. Choisis-en une autre."
            )

        return slug

    def clean_shop_name(self):
        name = (self.cleaned_data.get("shop_name") or "").strip()
        if len(name) < 2:
            raise ValidationError("Le nom de boutique doit faire au moins 2 caractères.")
        return name
