"""
Service panier — stockage session.

Structure stockée dans request.session["cart"] :
{
    "shop_id": 42,
    "items": {
        "<product_id>": {"quantity": 2, "unit_price": 5000, "name": "..."}
    }
}

Un panier est lié à UNE seule boutique : si l'utilisateur ajoute un
produit d'une autre boutique, l'ancien panier est remplacé (règle
métier à confirmer avec le client).
"""


CART_SESSION_KEY = "cart"


class Cart:
    def __init__(self, request):
        self.session = request.session
        cart = self.session.get(CART_SESSION_KEY)
        if not cart:
            cart = {"shop_id": None, "items": {}}
            self.session[CART_SESSION_KEY] = cart
        self.cart = cart

    def add(self, product, quantity: int = 1):
        """Ajoute un produit au panier (ou incrémente la quantité)."""
        # Un panier = une boutique. Si on change de boutique, on reset.
        if self.cart["shop_id"] and self.cart["shop_id"] != product.shop_id:
            self.cart = {"shop_id": product.shop_id, "items": {}}

        self.cart["shop_id"] = product.shop_id
        pid = str(product.id)
        existing = self.cart["items"].get(pid)
        if existing:
            existing["quantity"] += quantity
        else:
            self.cart["items"][pid] = {
                "quantity": quantity,
                "unit_price": product.price,
                "name": product.name,
            }
        self._save()

    def remove(self, product_id):
        self.cart["items"].pop(str(product_id), None)
        if not self.cart["items"]:
            self.cart["shop_id"] = None
        self._save()

    def clear(self):
        self.cart = {"shop_id": None, "items": {}}
        self.session[CART_SESSION_KEY] = self.cart
        self._save()

    @property
    def total_xof(self) -> int:
        return sum(item["unit_price"] * item["quantity"] for item in self.cart["items"].values())

    @property
    def item_count(self) -> int:
        return sum(item["quantity"] for item in self.cart["items"].values())

    def __iter__(self):
        for pid, item in self.cart["items"].items():
            yield {"product_id": int(pid), **item, "line_total": item["unit_price"] * item["quantity"]}

    def __len__(self):
        return self.item_count

    def _save(self):
        self.session[CART_SESSION_KEY] = self.cart
        self.session.modified = True
