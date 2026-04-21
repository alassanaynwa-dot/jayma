"""
Génère les icônes PWA à partir d'une lettre + couleur, via Pillow.
Produit : static/icons/icon-192.png, icon-512.png, icon-maskable-512.png, favicon.png
"""
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Génère les icônes PWA (192, 512, maskable) dans static/icons/"

    def handle(self, *args, **options):
        from PIL import Image, ImageDraw, ImageFont

        out = Path(settings.BASE_DIR) / "static" / "icons"
        out.mkdir(parents=True, exist_ok=True)

        # Palette Jayma
        BG = (196, 92, 42)       # jayma-500 orange brique
        FG = (255, 255, 255)     # blanc
        MASKABLE_SCALE = 0.68    # safe area pour maskable

        def _font(size):
            # Tente Playfair Display puis fallback DejaVu
            candidates = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
            ]
            for path in candidates:
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    continue
            return ImageFont.load_default()

        def draw_icon(size: int, letter: str = "J", rounded: bool = True, maskable: bool = False):
            img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            if maskable:
                # Fond plein (pas d'arrondi) — maskable doit couvrir tout
                draw.rectangle((0, 0, size, size), fill=BG)
                inner_size = int(size * MASKABLE_SCALE)
            elif rounded:
                radius = int(size * 0.22)
                draw.rounded_rectangle((0, 0, size, size), radius=radius, fill=BG)
                inner_size = size
            else:
                draw.rectangle((0, 0, size, size), fill=BG)
                inner_size = size

            # Lettre J centrée
            font = _font(int(inner_size * 0.62))
            bbox = draw.textbbox((0, 0), letter, font=font)
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            x = (size - w) / 2 - bbox[0]
            y = (size - h) / 2 - bbox[1] - int(size * 0.02)
            draw.text((x, y), letter, fill=FG, font=font)
            return img

        # Exports
        draw_icon(192).save(out / "icon-192.png", "PNG")
        draw_icon(512).save(out / "icon-512.png", "PNG")
        draw_icon(512, maskable=True).save(out / "icon-maskable-512.png", "PNG")
        draw_icon(64).save(out / "favicon.png", "PNG")

        self.stdout.write(self.style.SUCCESS(
            f"✓ Icônes PWA générées dans {out} :\n"
            f"  - icon-192.png\n  - icon-512.png\n  - icon-maskable-512.png\n  - favicon.png"
        ))
