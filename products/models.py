"""
Modèles products — catalogue par boutique.

Chaque Category et chaque Product appartiennent à un Shop (isolation tenant).
Prix en XOF entiers (PositiveIntegerField), jamais de décimales.
"""
from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    """Catégorie propre à une boutique."""

    shop = models.ForeignKey(
        "shops.Shop",
        on_delete=models.CASCADE,
        related_name="categories",
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    position = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"
        unique_together = [("shop", "slug")]
        ordering = ("position", "name")

    def __str__(self):
        return f"{self.name} — {self.shop.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:100] or "categorie"
            slug = base
            i = 2
            while Category.objects.filter(shop=self.shop, slug=slug).exclude(pk=self.pk).exists():
                suffix = f"-{i}"
                slug = f"{base[: 100 - len(suffix)]}{suffix}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)


class Product(models.Model):
    """Produit d'une boutique — prix en XOF entier. Peut être simple ou pack."""

    class Kind(models.TextChoices):
        SIMPLE = "simple", "Produit simple"
        PACK = "pack", "Pack de produits"

    shop = models.ForeignKey(
        "shops.Shop",
        on_delete=models.CASCADE,
        related_name="products",
    )
    category = models.ForeignKey(
        Category,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="products",
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200)
    description = models.TextField(blank=True)

    kind = models.CharField(
        max_length=10,
        choices=Kind.choices,
        default=Kind.SIMPLE,
    )
    # Pour les packs : les produits inclus, avec leur quantité (via PackItem)
    pack_items = models.ManyToManyField(
        "self",
        through="PackItem",
        through_fields=("pack", "item"),
        symmetrical=False,
        related_name="in_packs",
        blank=True,
    )

    # Prix en XOF entiers — JAMAIS de décimales pour l'argent
    price = models.PositiveIntegerField(help_text="Prix en XOF (entier). Pour un pack : prix total du pack.")
    compare_at_price = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Prix barré (promo), optionnel. Pour un pack : somme des prix individuels.",
    )

    stock = models.PositiveIntegerField(default=0)
    track_stock = models.BooleanField(
        default=True,
        help_text="Si désactivé, le produit est toujours en stock. Ignoré pour les packs.",
    )

    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False, help_text="Mis en avant sur l'accueil boutique.")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Produit"
        verbose_name_plural = "Produits"
        unique_together = [("shop", "slug")]
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["shop", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} — {self.price} XOF"

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:200] or "produit"
            slug = base
            i = 2
            while Product.objects.filter(shop=self.shop, slug=slug).exclude(pk=self.pk).exists():
                suffix = f"-{i}"
                slug = f"{base[: 200 - len(suffix)]}{suffix}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def is_available(self) -> bool:
        """Disponible à la vente ?"""
        if not self.is_active:
            return False
        if self.kind == self.Kind.PACK:
            # Un pack est disponible si tous ses sous-produits le sont
            for item in self.items_in_pack.select_related("item"):
                sub = item.item
                if not sub.is_active:
                    return False
                if sub.track_stock and sub.stock < item.quantity:
                    return False
            return True
        if self.track_stock and self.stock <= 0:
            return False
        return True

    @property
    def is_pack(self) -> bool:
        return self.kind == self.Kind.PACK

    def total_savings(self) -> int:
        """Pour un pack : combien on économise par rapport aux prix individuels."""
        if not self.is_pack:
            return 0
        total = sum(item.item.price * item.quantity for item in self.items_in_pack.all())
        return max(total - self.price, 0)

    @property
    def primary_image(self):
        """Image principale, ou première image, ou None."""
        return (
            self.images.filter(is_primary=True).first()
            or self.images.first()
        )

    @property
    def rating_summary(self) -> dict:
        """Retourne {avg, count} des avis approuvés pour ce produit."""
        qs = self.reviews.filter(is_approved=True)
        count = qs.count()
        if count == 0:
            return {"avg": None, "count": 0}
        total = sum(r.rating for r in qs)
        return {"avg": round(total / count, 1), "count": count}


class PackItem(models.Model):
    """Composition d'un pack : tel produit en telle quantité."""
    pack = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="items_in_pack",
        limit_choices_to={"kind": "pack"},
    )
    item = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="+",
        limit_choices_to={"kind": "simple"},
    )
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "Élément de pack"
        verbose_name_plural = "Éléments de packs"
        unique_together = [("pack", "item")]

    def __str__(self):
        return f"{self.pack.name} — {self.item.name} × {self.quantity}"


class ProductImage(models.Model):
    """Image(s) d'un produit — plusieurs possibles."""

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(upload_to="products/")
    alt_text = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    position = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Image produit"
        verbose_name_plural = "Images produits"
        ordering = ("position", "created_at")

    def __str__(self):
        return f"Image #{self.pk} de {self.product.name}"


class Favorite(models.Model):
    """Un produit mis en favori par un user client."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorites",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="favorited_by",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Favori"
        verbose_name_plural = "Favoris"
        unique_together = [("user", "product")]
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.user.username} ♥ {self.product.name}"


class StockAlert(models.Model):
    """
    Alerte « préviens-moi quand ce produit revient en stock ».

    Créée quand un client s'inscrit sur un produit épuisé. Le signal
    post_save sur Product détecte stock 0 → >0 et envoie les SMS.
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="stock_alerts",
    )
    client_phone = models.CharField(max_length=20, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Alerte retour en stock"
        verbose_name_plural = "Alertes retour en stock"
        unique_together = [("product", "client_phone")]
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["product", "notified_at"])]

    def __str__(self):
        return f"{self.client_phone} ← {self.product.name}"


class ProductReview(models.Model):
    """
    Avis d'un client sur un produit.

    Le client n'a pas forcément de compte — on l'identifie par téléphone.
    Vérification côté vue : le phone doit correspondre à une commande livrée
    contenant ce produit.
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="product_reviews",
        help_text="Commande qui prouve l'achat.",
    )
    client_phone = models.CharField(max_length=20, db_index=True)
    client_name = models.CharField(max_length=100)

    rating = models.PositiveSmallIntegerField(help_text="Note de 1 à 5 étoiles.")
    title = models.CharField(max_length=120, blank=True)
    comment = models.TextField(blank=True)

    is_approved = models.BooleanField(
        default=True,
        help_text="Le commerçant peut modérer les avis depuis son dashboard.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Avis produit"
        verbose_name_plural = "Avis produits"
        ordering = ("-created_at",)
        unique_together = [("product", "client_phone")]
        indexes = [models.Index(fields=["product", "is_approved"])]

    def __str__(self):
        return f"{self.rating}★ — {self.product.name} par {self.client_phone}"
