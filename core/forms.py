"""Formulaires publics jappesi.sn."""
from django import forms
from django.core.exceptions import ValidationError
from django.utils.text import slugify

from accounts.models import normalize_phone_sn
from config.middleware import RESERVED_SUBDOMAINS
from shops.models import Shop, ShopRequest

SLUG_MAX_LENGTH = 40
SLUG_MIN_LENGTH = 3


class ShopRequestForm(forms.ModelForm):
    """Formulaire de demande de création d'une boutique.

    Le slug (adresse en ligne) est calculé automatiquement à partir du nom de
    la boutique. Si le slug auto-généré est déjà pris, on suffixe -2, -3, etc.
    """

    terms_accepted = forms.BooleanField(
        required=True,
        label="J'accepte les conditions de Jappesi (commission 8%).",
    )

    class Meta:
        model = ShopRequest
        # `desired_slug` n'est PAS dans la liste : il est calculé en save()
        fields = [
            "full_name", "email", "phone", "city",
            "shop_name",
            "product_category", "description",
        ]
        labels = {
            "full_name": "Ton nom complet",
            "email": "Email",
            "phone": "Téléphone (Sénégal)",
            "city": "Ville",
            "shop_name": "Nom de ta boutique",
            "product_category": "Que vends-tu ?",
            "description": "Décris ta boutique (optionnel)",
        }
        help_texts = {
            "shop_name": "Le nom servira aussi d'adresse en ligne (ex : « Chez Awa » → chez-awa.jappesi.sn).",
            "phone": "Format : +221 77 123 45 67",
            "product_category": "Ex : vêtements, cosmétiques, électronique...",
        }
        widgets = {
            "full_name":        forms.TextInput(attrs={"class": "input", "placeholder": "Awa Diop"}),
            "email":            forms.EmailInput(attrs={"class": "input", "placeholder": "awa@exemple.sn"}),
            "phone":            forms.TextInput(attrs={"class": "input", "placeholder": "+221 77 123 45 67"}),
            "city":             forms.TextInput(attrs={"class": "input", "placeholder": "Dakar"}),
            "shop_name":        forms.TextInput(attrs={"class": "input", "placeholder": "Chez Awa", "id": "id_shop_name"}),
            "product_category": forms.TextInput(attrs={"class": "input", "placeholder": "Vêtements"}),
            "description":      forms.Textarea(attrs={"class": "input", "rows": 3, "placeholder": "Optionnel"}),
        }

    def clean_phone(self):
        return normalize_phone_sn(self.cleaned_data.get("phone"))

    def clean_shop_name(self):
        """Valide le nom ET garantit qu'il produit un slug acceptable."""
        name = (self.cleaned_data.get("shop_name") or "").strip()
        if len(name) < 2:
            raise ValidationError("Le nom de boutique doit faire au moins 2 caractères.")

        # Vérifie que le nom est slugifiable
        slug = slugify(name)
        if not slug or len(slug) < SLUG_MIN_LENGTH:
            raise ValidationError(
                f"Ce nom ne peut pas être transformé en adresse web. "
                f"Utilise des lettres ou chiffres (au moins {SLUG_MIN_LENGTH} caractères significatifs)."
            )

        # Le slug auto ne doit pas être un sous-domaine réservé même tronqué
        base = slug[:SLUG_MAX_LENGTH]
        if base in RESERVED_SUBDOMAINS:
            raise ValidationError(
                f"« {name} » correspond à un sous-domaine réservé par Jappesi. "
                f"Choisis un autre nom."
            )

        return name

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.desired_slug = self._compute_unique_slug(instance.shop_name)
        if commit:
            instance.save()
        return instance

    @staticmethod
    def _compute_unique_slug(shop_name: str) -> str:
        """Calcule un slug unique à partir du nom de la boutique.

        Si le slug de base est déjà pris (par une boutique active OU une
        demande en attente), on suffixe -2, -3, etc.
        """
        base = slugify(shop_name)[:SLUG_MAX_LENGTH] or "boutique"
        slug = base
        i = 2
        while _slug_is_taken(slug):
            suffix = f"-{i}"
            slug = f"{base[: SLUG_MAX_LENGTH - len(suffix)]}{suffix}"
            i += 1
            if i > 9999:  # safety net
                raise ValidationError("Trop de tentatives pour générer un slug unique.")
        return slug


def _slug_is_taken(slug: str) -> bool:
    """Indique si un slug est déjà pris par une Shop ou une demande en attente."""
    if Shop.objects.filter(slug=slug).exists():
        return True
    if ShopRequest.objects.filter(
        desired_slug=slug, status=ShopRequest.Status.PENDING
    ).exists():
        return True
    return False
