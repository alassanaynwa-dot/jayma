"""Vues products — côté dashboard commerçant et côté boutique publique."""
from django.contrib import messages
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import merchant_required

from .forms import (
    CategoryForm,
    PackForm,
    ProductForm,
    ProductImageFormSet,
    build_pack_item_formset,
)
from .models import Category, Product

# ======================== BOUTIQUE PUBLIQUE ========================

def product_list_public(request):
    """Catalogue d'une boutique sur <slug>.jappesi.sn."""
    if not request.shop:
        raise Http404()
    shop = request.shop
    products = shop.products.filter(is_active=True).select_related("category").prefetch_related("images", "items_in_pack__item")

    q = request.GET.get("q", "").strip()
    cat_slug = request.GET.get("cat", "").strip()
    active_category = None

    if q:
        products = products.filter(Q(name__icontains=q) | Q(description__icontains=q))
    if cat_slug:
        active_category = shop.categories.filter(slug=cat_slug).first()
        if active_category:
            # Si c'est un univers parent, on inclut TOUS les produits de ses
            # sous-catégories. Si c'est une sous-cat, on filtre juste dessus.
            cats_to_filter = active_category.get_descendant_categories()
            products = products.filter(category__in=cats_to_filter)

    # Pour la nav publique : seulement les racines (univers), avec leurs enfants préchargés
    from django.db.models import Prefetch
    nav_categories = (
        shop.categories.filter(is_active=True, parent__isnull=True)
        .order_by("position", "name")
        .prefetch_related(Prefetch(
            "children",
            queryset=Category.objects.filter(is_active=True).order_by("position", "name"),
        ))
    )

    return render(request, "products/list_public.html", {
        "shop": shop,
        "products": products,
        "categories": shop.categories.filter(is_active=True),  # legacy compat
        "nav_categories": nav_categories,
        "active_category": active_category,
        "q": q,
    })


def product_detail_public(request, slug):
    """Fiche produit d'une boutique."""
    if not request.shop:
        raise Http404()
    product = get_object_or_404(
        Product.objects.prefetch_related("images"),
        shop=request.shop,
        slug=slug,
        is_active=True,
    )
    images = list(product.images.all())
    primary = product.primary_image
    if primary and primary in images:
        images.remove(primary)
        images.insert(0, primary)

    discount_pct = None
    if product.compare_at_price and product.compare_at_price > product.price:
        discount_pct = round((1 - product.price / product.compare_at_price) * 100)

    related = (
        Product.objects
        .filter(shop=request.shop, is_active=True, category=product.category)
        .exclude(pk=product.pk)
        .prefetch_related("images")[:4]
    )

    return render(request, "products/detail_public.html", {
        "shop": request.shop,
        "product": product,
        "images": images,
        "discount_pct": discount_pct,
        "related": related,
    })


# ======================== DASHBOARD COMMERÇANT ========================

@merchant_required
def product_list_dashboard(request):
    """Liste des produits du commerçant avec recherche."""
    shop = request.merchant_shop
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")

    products = shop.products.select_related("category").prefetch_related("images")
    if q:
        products = products.filter(Q(name__icontains=q) | Q(description__icontains=q))
    if status == "active":
        products = products.filter(is_active=True)
    elif status == "inactive":
        products = products.filter(is_active=False)
    elif status == "low_stock":
        products = products.filter(track_stock=True, stock__lte=5, is_active=True)

    return render(request, "dashboard/products/list.html", {
        "shop": shop,
        "products": products,
        "q": q,
        "status": status,
    })


@merchant_required
def product_create(request):
    shop = request.merchant_shop
    if request.method == "POST":
        form = ProductForm(request.POST, shop=shop)
        image_formset = ProductImageFormSet(request.POST, request.FILES, instance=Product())
        if form.is_valid():
            product = form.save()
            image_formset.instance = product
            if image_formset.is_valid():
                image_formset.save()
            messages.success(request, f"Produit « {product.name} » ajouté.")
            return redirect("products_dashboard:list")
    else:
        form = ProductForm(shop=shop)
        image_formset = ProductImageFormSet(instance=Product())
    return render(request, "dashboard/products/form.html", {
        "shop": shop, "form": form, "image_formset": image_formset, "product": None,
    })


@merchant_required
def product_edit(request, pk):
    shop = request.merchant_shop
    product = get_object_or_404(Product, pk=pk, shop=shop)
    if request.method == "POST":
        form = ProductForm(request.POST, instance=product, shop=shop)
        image_formset = ProductImageFormSet(request.POST, request.FILES, instance=product)
        if form.is_valid() and image_formset.is_valid():
            form.save()
            image_formset.save()
            messages.success(request, "Produit mis à jour.")
            return redirect("products_dashboard:list")
    else:
        form = ProductForm(instance=product, shop=shop)
        image_formset = ProductImageFormSet(instance=product)
    return render(request, "dashboard/products/form.html", {
        "shop": shop, "form": form, "image_formset": image_formset, "product": product,
    })


@merchant_required
@require_POST
def product_delete(request, pk):
    shop = request.merchant_shop
    product = get_object_or_404(Product, pk=pk, shop=shop)
    name = product.name
    product.delete()
    messages.success(request, f"Produit « {name} » supprimé.")
    return redirect("products_dashboard:list")


@merchant_required
@require_POST
def product_toggle_active(request, pk):
    shop = request.merchant_shop
    product = get_object_or_404(Product, pk=pk, shop=shop)
    product.is_active = not product.is_active
    product.save(update_fields=["is_active", "updated_at"])
    return render(request, "dashboard/products/_row.html", {"product": product})


# ======================== PACKS (dashboard) ========================

@merchant_required
def pack_list(request):
    shop = request.merchant_shop
    packs = shop.products.filter(kind=Product.Kind.PACK).prefetch_related("items_in_pack__item")
    return render(request, "dashboard/products/packs_list.html", {
        "shop": shop, "packs": packs,
    })


@merchant_required
def pack_create(request):
    shop = request.merchant_shop
    PackItemFormSet = build_pack_item_formset(shop)
    if request.method == "POST":
        form = PackForm(request.POST, shop=shop)
        items_formset = PackItemFormSet(request.POST, instance=Product())
        if form.is_valid():
            pack = form.save()
            items_formset.instance = pack
            if items_formset.is_valid():
                items_formset.save()
                messages.success(request, f"Pack « {pack.name} » créé.")
                return redirect("products_dashboard:pack_list")
    else:
        form = PackForm(shop=shop)
        items_formset = PackItemFormSet(instance=Product())
    return render(request, "dashboard/products/packs_form.html", {
        "shop": shop, "form": form, "items_formset": items_formset, "pack": None,
    })


@merchant_required
def pack_edit(request, pk):
    shop = request.merchant_shop
    pack = get_object_or_404(Product, pk=pk, shop=shop, kind=Product.Kind.PACK)
    PackItemFormSet = build_pack_item_formset(shop)
    if request.method == "POST":
        form = PackForm(request.POST, instance=pack, shop=shop)
        items_formset = PackItemFormSet(request.POST, instance=pack)
        if form.is_valid() and items_formset.is_valid():
            form.save()
            items_formset.save()
            messages.success(request, "Pack mis à jour.")
            return redirect("products_dashboard:pack_list")
    else:
        form = PackForm(instance=pack, shop=shop)
        items_formset = PackItemFormSet(instance=pack)
    return render(request, "dashboard/products/packs_form.html", {
        "shop": shop, "form": form, "items_formset": items_formset, "pack": pack,
    })


@merchant_required
@require_POST
def pack_delete(request, pk):
    shop = request.merchant_shop
    pack = get_object_or_404(Product, pk=pk, shop=shop, kind=Product.Kind.PACK)
    name = pack.name
    pack.delete()
    messages.success(request, f"Pack « {name} » supprimé.")
    return redirect("products_dashboard:pack_list")


# ======================== CATÉGORIES (dashboard) ========================

@merchant_required
def category_list(request):
    """Liste catégories du dashboard, en liste plate ordonnée par hiérarchie.

    Ordre rendu : pour chaque univers (parent=null), d'abord l'univers lui-même
    puis ses sous-catégories juste après. Les catégories orphelines (parent=null
    sans enfants, créées manuellement) apparaissent au même niveau que les
    univers.

    On enrichit chaque objet d'un attribut `parent_label` = nom du parent
    (ou None) pour l'affichage de la pill.
    """
    shop = request.merchant_shop
    flat = []
    roots = list(
        shop.categories.filter(parent__isnull=True).order_by("position", "name")
    )
    for root in roots:
        root.parent_label = None
        flat.append(root)
        for child in root.children.order_by("position", "name"):
            child.parent_label = root.name
            child.parent_emoji = root.emoji
            flat.append(child)

    return render(request, "dashboard/categories/list.html", {
        "shop": shop,
        "categories": flat,
        "total_count": len(flat),
        "show_wizard_promo": len(flat) == 0,
    })


@merchant_required
@require_POST
def category_bulk_delete(request):
    """Supprime en lot les catégories cochées par le commerçant.

    Si on supprime un univers, ses sous-cat passent en orphelines (parent
    devient NULL grâce au on_delete=SET_NULL du modèle), elles ne sont
    PAS supprimées en cascade. Les produits liés perdent leur catégorie
    (category devient NULL, comportement existant du modèle).
    """
    ids_raw = request.POST.getlist("selected_ids[]") or request.POST.getlist("selected_ids")
    shop = request.merchant_shop
    valid_ids = []
    for raw in ids_raw:
        try:
            valid_ids.append(int(raw))
        except (TypeError, ValueError):
            continue
    if not valid_ids:
        messages.error(request, "Aucune catégorie sélectionnée.")
        return redirect("products_dashboard:category_list")

    deleted, _ = Category.objects.filter(pk__in=valid_ids, shop=shop).delete()
    if deleted:
        messages.success(
            request,
            f"{deleted} catégorie{'s' if deleted > 1 else ''} supprimée{'s' if deleted > 1 else ''}.",
        )
    return redirect("products_dashboard:category_list")


@merchant_required
def category_wizard(request):
    """Onboarding catégories : sélection de 1 à 5 univers → arborescence créée.

    Pour chaque univers, on crée la catégorie racine (l'univers lui-même, avec
    son emoji) puis ses sous-catégories enfants. Idempotent : on s'appuie sur
    get_or_create avec un slug pré-calculé pour ne pas dupliquer.
    """
    from django.utils.text import slugify

    from products.data.category_templates import CATEGORY_TEMPLATES, get_template_by_key

    shop = request.merchant_shop
    if request.method == "POST":
        selected_keys = request.POST.getlist("universe")
        if not selected_keys:
            messages.error(request, "Sélectionne au moins un univers.")
            return redirect("products_dashboard:category_wizard")
        if len(selected_keys) > 5:
            messages.error(request, "Maximum 5 univers à la fois.")
            return redirect("products_dashboard:category_wizard")

        position_offset = shop.categories.count()
        added = 0
        for key in selected_keys:
            tpl = get_template_by_key(key)
            if not tpl:
                continue
            # 1. Créer ou récupérer la catégorie racine (univers)
            parent_slug = slugify(tpl["label"])[:100]
            parent, parent_created = Category.objects.get_or_create(
                shop=shop, slug=parent_slug,
                defaults={
                    "name": tpl["label"],
                    "emoji": tpl["emoji"],
                    "position": position_offset + added,
                    "is_active": True,
                },
            )
            if parent_created:
                added += 1
            # 2. Créer les sous-catégories enfants
            for sub_name in tpl["subcategories"]:
                sub_slug = slugify(sub_name)[:100]
                _, created = Category.objects.get_or_create(
                    shop=shop, slug=sub_slug,
                    defaults={
                        "name": sub_name,
                        "parent": parent,
                        "position": position_offset + added,
                        "is_active": True,
                    },
                )
                if created:
                    added += 1
        messages.success(
            request,
            f"{added} catégorie{'s' if added > 1 else ''} ajoutée{'s' if added > 1 else ''} à ta boutique. "
            f"Tu peux les modifier, les réordonner ou en supprimer à tout moment.",
        )
        return redirect("products_dashboard:category_list")

    return render(request, "dashboard/categories/wizard.html", {
        "shop": shop,
        "templates": CATEGORY_TEMPLATES,
        "existing_count": shop.categories.count(),
    })


@merchant_required
def category_create(request):
    shop = request.merchant_shop
    if request.method == "POST":
        form = CategoryForm(request.POST, shop=shop)
        if form.is_valid():
            cat = form.save()
            messages.success(request, f"Catégorie « {cat.name} » créée.")
            return redirect("products_dashboard:category_list")
    else:
        # Pré-remplir parent via query string ?parent=<id> (utilisé par "Ajouter une sous-cat")
        initial = {}
        parent_id = request.GET.get("parent")
        if parent_id:
            try:
                Category.objects.get(pk=int(parent_id), shop=shop, parent__isnull=True)
                initial["parent"] = parent_id
            except (Category.DoesNotExist, ValueError, TypeError):
                pass
        form = CategoryForm(shop=shop, initial=initial)
    return render(request, "dashboard/categories/form.html", {"shop": shop, "form": form, "category": None})


@merchant_required
def category_edit(request, pk):
    shop = request.merchant_shop
    cat = get_object_or_404(Category, pk=pk, shop=shop)
    if request.method == "POST":
        form = CategoryForm(request.POST, instance=cat, shop=shop)
        if form.is_valid():
            form.save()
            messages.success(request, "Catégorie mise à jour.")
            return redirect("products_dashboard:category_list")
    else:
        form = CategoryForm(instance=cat, shop=shop)
    return render(request, "dashboard/categories/form.html", {"shop": shop, "form": form, "category": cat})


@merchant_required
@require_POST
def category_delete(request, pk):
    shop = request.merchant_shop
    cat = get_object_or_404(Category, pk=pk, shop=shop)
    name = cat.name
    cat.delete()
    messages.success(request, f"Catégorie « {name} » supprimée.")
    return redirect("products_dashboard:category_list")
