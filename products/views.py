"""Vues products — côté dashboard commerçant et côté boutique publique."""
from django.contrib import messages
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import merchant_required

from .forms import (
    CategoryForm, PackForm, ProductForm, ProductImageFormSet,
    build_pack_item_formset,
)
from .models import Category, Product


# ======================== BOUTIQUE PUBLIQUE ========================

def product_list_public(request):
    """Catalogue d'une boutique sur <slug>.jayma.sn."""
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
            products = products.filter(category=active_category)

    return render(request, "products/list_public.html", {
        "shop": shop,
        "products": products,
        "categories": shop.categories.filter(is_active=True),
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
    shop = request.merchant_shop
    return render(request, "dashboard/categories/list.html", {
        "shop": shop, "categories": shop.categories.all(),
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
        form = CategoryForm(shop=shop)
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
