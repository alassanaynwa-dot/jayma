"""
Service checkout — transforme un panier session + formulaire en Order persistée.

Transactionnel : soit l'Order complète est créée avec toutes ses lignes
et la Commission associée, soit rien ne bouge.
"""
from django.db import transaction

from cart.services.cart import Cart
from commissions.models import Commission
from products.models import Product
from shops.models import Shop

from ..models import Order, OrderItem
from .pricing import compute_commission


class CheckoutError(Exception):
    pass


@transaction.atomic
def create_order_from_cart(request, shop: Shop, form_data: dict) -> Order:
    """
    Crée l'Order à partir du panier actuel + données checkout.

    Si le client a coché "Sauvegarder mes infos", on crée (ou retrouve) un
    User client et on sauvegarde l'adresse pour la prochaine fois.

    Ne déclenche pas l'appel de paiement (à faire en aval via payments/services/<provider>.py).
    """
    cart = Cart(request)
    if len(cart) == 0:
        raise CheckoutError("Le panier est vide.")
    if cart.cart.get("shop_id") != shop.id:
        raise CheckoutError("Le panier ne correspond pas à la boutique courante.")

    subtotal = cart.total_xof

    # Frais de livraison = tarif de la zone qui couvre la ville du client
    from delivery.services.zones import compute_delivery_fee
    delivery, _zone = compute_delivery_fee(shop, form_data["client_city"])

    # Coupon appliqué (stocké en session) — re-vérifié avec le phone client
    from coupons.services.application import (
        clear_session_coupon,
        compute_cart_discount,
    )
    coupon_result = compute_cart_discount(
        request, shop, subtotal, client_phone=form_data["client_phone"],
    )
    discount = coupon_result.discount_xof
    coupon_code = coupon_result.coupon.code if coupon_result.coupon else ""

    # Freeship = livraison mise à 0 (si coupon freeship applicable)
    if coupon_result.freeship:
        delivery = 0

    total = max(subtotal - discount + delivery, 0)

    rate = shop.commission_rate  # Decimal
    commission_xof, merchant_amount_xof = compute_commission(total, rate)

    order = Order.objects.create(
        shop=shop,
        client_name=form_data["client_name"],
        client_phone=form_data["client_phone"],
        client_email=form_data.get("client_email", ""),
        client_address=form_data["client_address"],
        client_city=form_data["client_city"],
        client_notes=form_data.get("client_notes", ""),
        subtotal_xof=subtotal,
        delivery_xof=delivery,
        discount_xof=discount,
        coupon_code=coupon_code,
        total_xof=total,
        commission_rate=rate,
        commission_xof=commission_xof,
        merchant_amount_xof=merchant_amount_xof,
        payment_method=form_data["payment_method"],
        payment_status=Order.PaymentStatus.PENDING,
    )

    # Créer les lignes et décrémenter le stock (sub-products si pack)
    for item in cart:
        product = Product.objects.select_for_update().filter(
            pk=item["product_id"], shop=shop
        ).first()
        if product is None:
            raise CheckoutError(f"Produit introuvable : {item['name']}.")

        # Vérif dispo + décrémentation selon le type
        if product.kind == Product.Kind.PACK:
            # Vérifier chaque sous-produit
            for pack_item in product.items_in_pack.select_related("item").all():
                sub = Product.objects.select_for_update().get(pk=pack_item.item_id)
                needed = pack_item.quantity * item["quantity"]
                if sub.track_stock and sub.stock < needed:
                    raise CheckoutError(
                        f"Stock insuffisant pour « {sub.name} » (dans le pack « {product.name} »)."
                    )
                if sub.track_stock:
                    sub.stock -= needed
                    sub.save(update_fields=["stock", "updated_at"])
        else:
            if product.track_stock and product.stock < item["quantity"]:
                raise CheckoutError(f"Stock insuffisant pour « {product.name} ».")
            if product.track_stock:
                product.stock -= item["quantity"]
                product.save(update_fields=["stock", "updated_at"])

        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=item["name"],
            unit_price_xof=item["unit_price"],
            quantity=item["quantity"],
        )

    # Commission (snapshot)
    Commission.objects.create(
        order=order,
        shop=shop,
        sale_amount_xof=total,
        rate=rate,
        commission_xof=commission_xof,
        merchant_amount_xof=merchant_amount_xof,
    )

    # Incrémenter le compteur + enregistrer l'utilisation (pour 1-per-customer)
    if coupon_result.coupon:
        coupon_result.coupon.uses_count = (coupon_result.coupon.uses_count or 0) + 1
        coupon_result.coupon.save(update_fields=["uses_count"])
        from coupons.models import CouponUsage
        CouponUsage.objects.create(
            coupon=coupon_result.coupon,
            order=order,
            client_phone=form_data["client_phone"],
            discount_xof=discount,
        )

    # Sauvegarder l'adresse si le client l'a demandé
    if form_data.get("save_profile"):
        from accounts.models import ClientAddress, User
        phone = form_data["client_phone"]
        user, created = User.objects.get_or_create(
            phone=phone,
            defaults={
                "username": f"client_{phone.lstrip('+')}",
                "role": User.Role.CLIENT,
                "first_name": form_data["client_name"].split(" ")[0] if form_data.get("client_name") else "",
                "email": form_data.get("client_email", ""),
                "city": form_data["client_city"],
            },
        )
        if created:
            user.set_unusable_password()
            user.save()

        # Si pas déjà d'adresse à cet endroit, on la sauvegarde
        exists = ClientAddress.objects.filter(
            user=user, address=form_data["client_address"], city=form_data["client_city"],
        ).exists()
        if not exists:
            ClientAddress.objects.create(
                user=user,
                label="Adresse de livraison",
                address=form_data["client_address"],
                city=form_data["client_city"],
                is_default=not user.addresses.exists(),
            )

    # Vider le panier + le coupon session
    cart.clear()
    clear_session_coupon(request.session)

    return order
