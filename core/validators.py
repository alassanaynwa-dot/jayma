"""Validateurs réutilisables pour Django models / forms.

En particulier les uploads d'images, où il faut limiter l'extension et
la taille pour éviter qu'un commerçant uploade un .exe renommé en .png
ou un fichier de 50MB qui sature le disque.
"""
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

# Extensions autorisées pour toutes les images uploadées (logos, banners,
# photos produits). On exclut .gif (rarement utile) et formats exotiques.
ALLOWED_IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "webp"]

# Taille max d'un upload image, en octets. 5 MB suffit largement pour une
# photo produit prise au téléphone (la plupart des smartphones produisent
# des JPG de 1-3 MB pour 12 Mpx). Au-delà, on refuse pour préserver le
# stockage et la bande passante mobile des clients qui chargent les pages.
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


image_extension_validator = FileExtensionValidator(
    allowed_extensions=ALLOWED_IMAGE_EXTENSIONS,
    message=(
        "Format non supporté. Formats acceptés : "
        + ", ".join(f".{e}" for e in ALLOWED_IMAGE_EXTENSIONS)
    ),
)


def validate_image_size(file) -> None:
    """Lève ValidationError si l'image dépasse MAX_IMAGE_SIZE_BYTES.

    À utiliser dans validators=[...] d'un ImageField. Le check se fait
    avant que le fichier ne soit copié dans MEDIA_ROOT, donc ne consomme
    pas d'espace disque.
    """
    if file and file.size > MAX_IMAGE_SIZE_BYTES:
        size_mb = file.size / (1024 * 1024)
        max_mb = MAX_IMAGE_SIZE_BYTES / (1024 * 1024)
        raise ValidationError(
            f"Image trop lourde ({size_mb:.1f} MB). "
            f"Taille max : {max_mb:.0f} MB. Compresse avant d'uploader."
        )


# Tuple à passer directement à validators=[*IMAGE_VALIDATORS] sur un ImageField.
IMAGE_VALIDATORS = (image_extension_validator, validate_image_size)
