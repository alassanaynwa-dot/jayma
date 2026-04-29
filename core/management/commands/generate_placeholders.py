"""
Génère des images placeholder pour les produits sans photo, via Pillow.

Chaque image (800x800 PNG) combine :
- Un fond dégradé couleur de catégorie
- Un motif décoratif (cercles concentriques subtils)
- Une grande initiale en serif au centre
- Le nom du produit en bas

Usage :
    python manage.py generate_placeholders              # tous les shops
    python manage.py generate_placeholders --slug=chez-fatou  # un shop
    python manage.py generate_placeholders --force       # régénère même si l'image existe
"""
import io
import random

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from products.models import Product, ProductImage

# Palette couleurs (fond, fond-bas, accent) par slug de catégorie
CATEGORY_PALETTE = {
    "vetements":   ((122, 46, 46),   (90, 30, 30),   (230, 180, 120)),   # wine → burgundy
    "cosmetiques": ((196, 92, 42),   (150, 65, 30),  (255, 230, 200)),   # terracotta (jayma)
    "epicerie":    ((107, 125, 92),  (75, 90, 65),   (200, 220, 170)),   # sage green
    "boissons":    ((46, 107, 125),  (30, 75, 90),   (180, 220, 230)),   # teal
    "bijoux":      ((184, 134, 11),  (130, 95, 10),  (255, 230, 170)),   # gold
    "maison":      ((74, 90, 122),   (55, 68, 92),   (200, 210, 230)),   # slate blue
}
DEFAULT_PALETTE = ((196, 92, 42), (150, 65, 30), (255, 230, 200))


def _font(size: int):
    from PIL import ImageFont
    for path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _wrap_text(text: str, font, draw, max_width: int) -> list[str]:
    """Découpe le texte en lignes qui tiennent dans max_width."""
    words = text.split()
    lines, current = [], ""
    for w in words:
        candidate = (current + " " + w).strip()
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines[:2]  # max 2 lignes


def make_placeholder(name: str, category_slug: str | None, size: int = 800) -> bytes:
    from PIL import Image, ImageDraw

    color_top, color_bot, accent = CATEGORY_PALETTE.get(category_slug or "", DEFAULT_PALETTE)

    img = Image.new("RGB", (size, size), color_top)
    draw = ImageDraw.Draw(img, "RGBA")

    # Dégradé vertical
    for y in range(size):
        t = y / size
        r = int(color_top[0] * (1 - t) + color_bot[0] * t)
        g = int(color_top[1] * (1 - t) + color_bot[1] * t)
        b = int(color_top[2] * (1 - t) + color_bot[2] * t)
        draw.line([(0, y), (size, y)], fill=(r, g, b))

    # Cercles décoratifs subtils (semi-transparents)
    rng = random.Random(hash(name))
    for _ in range(3):
        cx = rng.randint(int(size * 0.1), int(size * 0.9))
        cy = rng.randint(int(size * 0.1), int(size * 0.9))
        radius = rng.randint(int(size * 0.15), int(size * 0.35))
        alpha = rng.randint(15, 35)
        draw.ellipse(
            [(cx - radius, cy - radius), (cx + radius, cy + radius)],
            fill=(255, 255, 255, alpha),
        )

    # Grande initiale au centre
    initial = (name.strip()[:1] or "?").upper()
    font_big = _font(int(size * 0.45))
    bbox = draw.textbbox((0, 0), initial, font=font_big)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - w) / 2 - bbox[0]
    y = (size - h) / 2 - bbox[1] - int(size * 0.05)
    # Ombre légère pour contraste
    draw.text((x + 3, y + 3), initial, fill=(0, 0, 0, 60), font=font_big)
    draw.text((x, y), initial, fill=accent, font=font_big)

    # Nom du produit en bas (wrapping auto, max 2 lignes)
    font_name = _font(int(size * 0.042))
    max_line_width = int(size * 0.82)
    lines = _wrap_text(name, font_name, draw, max_line_width)
    total_h = sum(draw.textbbox((0, 0), ln, font=font_name)[3] for ln in lines) + 5 * (len(lines) - 1)
    start_y = size - int(size * 0.13) - total_h
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font_name)
        lw = bbox[2] - bbox[0]
        lx = (size - lw) / 2 - bbox[0]
        ly = start_y + i * (bbox[3] + 3)
        draw.text((lx, ly), line, fill=(255, 255, 255, 235), font=font_name)

    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


class Command(BaseCommand):
    help = "Génère des images placeholder pour les produits sans photo."

    def add_arguments(self, parser):
        parser.add_argument("--slug", type=str, default=None, help="Slug boutique (sinon toutes)")
        parser.add_argument("--force", action="store_true", help="Régénère même si l'image existe")

    def handle(self, *args, **options):
        qs = Product.objects.select_related("category", "shop")
        if options["slug"]:
            qs = qs.filter(shop__slug=options["slug"])

        created = skipped = 0
        for product in qs:
            has_image = product.images.exists()
            if has_image and not options["force"]:
                skipped += 1
                continue
            if has_image and options["force"]:
                product.images.all().delete()

            cat_slug = product.category.slug if product.category else None
            data = make_placeholder(product.name, cat_slug)
            filename = f"placeholder_{product.shop.slug}_{product.slug}.png"

            img = ProductImage(product=product, is_primary=True)
            img.image.save(filename, ContentFile(data), save=True)
            created += 1

            self.stdout.write(f"  ✓ {product.name}")

        self.stdout.write(self.style.SUCCESS(
            f"\nTerminé : {created} image(s) générée(s), {skipped} ignorée(s)."
        ))
