"""Formulaires produits (dashboard commerçant)."""
from django import forms
from django.forms import inlineformset_factory

from .models import Category, PackItem, Product, ProductImage


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "name", "category", "description",
            "price", "compare_at_price",
            "stock", "track_stock",
            "is_active", "is_featured",
        ]
        labels = {
            "name": "Nom du produit",
            "category": "Catégorie",
            "description": "Description",
            "price": "Prix (XOF)",
            "compare_at_price": "Prix barré (XOF)",
            "stock": "Stock disponible",
            "track_stock": "Suivre le stock",
            "is_active": "Produit actif (visible)",
            "is_featured": "Mis en avant sur l'accueil boutique",
        }
        help_texts = {
            "compare_at_price": "Optionnel — prix avant promo.",
            "track_stock": "Si désactivé, produit toujours disponible.",
        }
        widgets = {
            "name":             forms.TextInput(attrs={"class": "input", "placeholder": "Ex : Boubou brodé"}),
            "category":         forms.Select(attrs={"class": "input"}),
            "description":      forms.Textarea(attrs={"class": "input", "rows": 4}),
            "price":            forms.NumberInput(attrs={"class": "input", "min": 0, "step": 1}),
            "compare_at_price": forms.NumberInput(attrs={"class": "input", "min": 0, "step": 1}),
            "stock":            forms.NumberInput(attrs={"class": "input", "min": 0, "step": 1}),
        }

    def __init__(self, *args, shop=None, **kwargs):
        self.shop = shop
        super().__init__(*args, **kwargs)
        if shop:
            self.fields["category"].queryset = Category.objects.filter(shop=shop, is_active=True)
            self.fields["category"].empty_label = "— Aucune —"

    def save(self, commit=True):
        product = super().save(commit=False)
        if self.shop:
            product.shop = self.shop
        if commit:
            product.save()
        return product


ProductImageFormSet = inlineformset_factory(
    Product,
    ProductImage,
    fields=("image", "is_primary"),
    extra=3,
    max_num=8,
    can_delete=True,
    widgets={
        "image": forms.FileInput(attrs={"class": "block w-full text-sm"}),
    },
)


class PackForm(forms.ModelForm):
    """Formulaire de création/édition d'un pack (Product avec kind=pack)."""

    class Meta:
        model = Product
        fields = ["name", "description", "price", "compare_at_price", "is_active", "is_featured"]
        labels = {
            "name": "Nom du pack",
            "description": "Description",
            "price": "Prix du pack (XOF)",
            "compare_at_price": "Prix barré (XOF)",
            "is_active": "Pack actif",
            "is_featured": "Mis en avant",
        }
        help_texts = {
            "compare_at_price": "Optionnel — par défaut, la somme des prix individuels.",
        }
        widgets = {
            "name":             forms.TextInput(attrs={"class": "input", "placeholder": "Pack découverte"}),
            "description":      forms.Textarea(attrs={"class": "input", "rows": 3}),
            "price":            forms.NumberInput(attrs={"class": "input", "min": 0, "step": 500}),
            "compare_at_price": forms.NumberInput(attrs={"class": "input", "min": 0, "step": 500}),
        }

    def __init__(self, *args, shop=None, **kwargs):
        self.shop = shop
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        pack = super().save(commit=False)
        pack.kind = Product.Kind.PACK
        pack.track_stock = False  # Stock calculé depuis les sous-produits
        if self.shop:
            pack.shop = self.shop
        if commit:
            pack.save()
        return pack


class _PackItemForm(forms.ModelForm):
    class Meta:
        model = PackItem
        fields = ("item", "quantity")
        widgets = {
            "item": forms.Select(attrs={"class": "input"}),
            "quantity": forms.NumberInput(attrs={"class": "input w-20", "min": 1, "value": 1}),
        }

    def __init__(self, *args, shop=None, **kwargs):
        super().__init__(*args, **kwargs)
        if shop:
            # Seuls les produits SIMPLES (pas les autres packs) peuvent être inclus
            self.fields["item"].queryset = shop.products.filter(
                kind=Product.Kind.SIMPLE, is_active=True,
            )


def build_pack_item_formset(shop):
    """Factory qui retourne un formset pré-configuré avec le queryset shop-scoped."""
    return inlineformset_factory(
        Product, PackItem,
        form=_PackItemForm,
        fk_name="pack",
        fields=("item", "quantity"),
        extra=3,
        max_num=10,
        can_delete=True,
        formset=type("_FS", (forms.BaseInlineFormSet,), {
            "_construct_form": lambda self, i, **kw: forms.BaseInlineFormSet._construct_form(self, i, shop=shop, **kw),
        }),
    )


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "position", "is_active"]
        labels = {
            "name": "Nom de la catégorie",
            "position": "Ordre d'affichage",
            "is_active": "Catégorie active",
        }
        widgets = {
            "name":     forms.TextInput(attrs={"class": "input", "placeholder": "Ex : Vêtements"}),
            "position": forms.NumberInput(attrs={"class": "input", "min": 0}),
        }

    def __init__(self, *args, shop=None, **kwargs):
        self.shop = shop
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        cat = super().save(commit=False)
        if self.shop:
            cat.shop = self.shop
        if commit:
            cat.save()
        return cat
