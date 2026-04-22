from django.apps import AppConfig


class ProductsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "products"
    verbose_name = "Catalogue produits"

    def ready(self):
        from . import signals  # noqa: F401
