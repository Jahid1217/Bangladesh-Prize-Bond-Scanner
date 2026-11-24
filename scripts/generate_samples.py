"""Generate realistic Bangladesh prize bond sample images for OCR tests.

Usage:
    python scripts/generate_samples.py --out tests/fixtures --count 6
"""

from __future__ import annotations

import argparse
import glob
import json
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]


def _font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont:
    for pattern in candidates:
        matches = sorted(glob.glob(pattern))
        if matches:
            return ImageFont.truetype(str(matches[0]), size)
    return ImageFont.load_default()


BENGALI_FONTS = [
    "/usr/share/fonts/truetype/noto/NotoSansBengali-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansBengali-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]
BENGALI_SERIAL_FONTS = [
    "/usr/share/fonts/truetype/noto/NotoSansBengali-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]
LATIN_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]
LATIN_MONO = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
]

BENGALI_DIGITS = "০১২৩৪৫৬৭৮৯"


def to_bengali(value: str) -> str:
    return "".join(BENGALI_DIGITS[int(ch)] if ch.isdigit() else ch for ch in value)


def render_bond(serial: str, *, bengali: bool = True, denomination: int = 200,
                width: int = 1400, height: int = 800, noise: float = 0.0) -> Image.Image:
    image = Image.new("RGB", (width, height), (250, 250, 244))
    draw = ImageDraw.Draw(image)

    # Ornamental border
    draw.rectangle([18, 18, width - 18, height - 18], outline=(22, 90, 70), width=5)
    draw.rectangle([32, 32, width - 32, height - 32], outline=(180, 140, 60), width=2)
    for step in range(0, width, 34):
        draw.line([(step, 18), (min(step + 17, width), 18)], fill=(22, 90, 70), width=2)
        draw.line([(step, height - 18), (min(step + 17, width), height - 18)],
                  fill=(22, 90, 70), width=2)

    title_font = _font(BENGALI_FONTS, 62)
    latin_title = _font(LATIN_FONTS, 30)
    label_font = _font(BENGALI_FONTS, 30)
    serial_font = _font(BENGALI_SERIAL_FONTS if bengali else LATIN_MONO, 118)
    latin_serial = _font(LATIN_MONO, 112)
    small_font = _font(LATIN_FONTS, 24)

    title = "বাংলাদেশ প্রাইজ বন্ড"
    box = draw.textbbox((0, 0), title, font=title_font)
    draw.text(((width - (box[2] - box[0])) / 2, 62), title, font=title_font,
              fill=(20, 70, 55))
    subtitle = "BANGLADESH PRIZE BOND"
    box = draw.textbbox((0, 0), subtitle, font=latin_title)
    draw.text(((width - (box[2] - box[0])) / 2, 148), subtitle, font=latin_title,
              fill=(90, 90, 86))

    draw.text((95, 250), "ক্রমিক নং", font=label_font, fill=(60, 60, 60))
    draw.text((95, 292), "Serial No.", font=small_font, fill=(90, 90, 90))

    shown = to_bengali(serial) if bengali else serial
    font = serial_font if bengali else latin_serial
    # Print digits with a little air between them, like the real bonds.
    spacing = 8 if bengali else 5
    advances = [draw.textlength(ch, font=font) for ch in shown]
    total = sum(advances) + spacing * (len(shown) - 1)
    x = (width - total) / 2
    for ch, advance in zip(shown, advances):
        draw.text((x, 350), ch, font=font, fill=(15, 35, 95))
        x += advance + spacing

    draw.line([(95, 520), (width - 95, 520)], fill=(180, 140, 60), width=2)
    draw.text((95, 560), f"মূল্য {to_bengali(str(denomination))} টাকা",
              font=label_font, fill=(60, 60, 60))
    draw.text((width - 420, 560), f"Taka {denomination}",
              font=small_font, fill=(90, 90, 90))
    draw.text((95, 640), "গণপ্রজাতন্ত্রী বাংলাদেশ সরকার",
              font=_font(BENGALI_FONTS, 28), fill=(60, 60, 60))
    draw.text((95, 690), "Government of the People's Republic of Bangladesh",
              font=_font(LATIN_FONTS, 20), fill=(110, 110, 110))
    draw.text((width - 330, 700), "ঢাকা • DHAKA", font=small_font, fill=(90, 90, 90))

    if noise > 0:
        pixels = image.load()
        rng = random.Random(serial)
        for _ in range(int(width * height * noise * 0.02)):
            x = rng.randrange(width)
            y = rng.randrange(height)
            r, g, b = pixels[x, y]
            delta = rng.randint(-18, 18)
            pixels[x, y] = (max(0, min(255, r + delta)),
                            max(0, min(255, g + delta)),
                            max(0, min(255, b + delta)))
        image = image.filter(ImageFilter.GaussianBlur(radius=0.4))
    return image


def serial_crop(image: Image.Image, width: int = 1400, height: int = 800) -> Image.Image:
    """Approximate what the phone sends after cropping to the guide frame."""
    return image.crop((int(width * 0.06), int(height * 0.40),
                       int(width * 0.94), int(height * 0.62)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="tests/fixtures")
    parser.add_argument("--count", type=int, default=6)
    parser.add_argument("--english", action="store_true",
                        help="Render serials with ASCII digits instead of Bengali")
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()

    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)

    manifest = []
    for index in range(args.count):
        if args.english:
            serial = f"{rng.randint(0, 9)}{rng.randint(100000, 999999)}"
        else:
            serial = f"{rng.randint(0, 9)}{rng.randint(100000, 999999)}"
        denomination = rng.choice([200, 400, 600, 1000])
        image = render_bond(serial, bengali=not args.english,
                            denomination=denomination, noise=0.2 if index % 2 else 0.0)
        bond_path = out / f"bond_{index + 1:02d}_{serial}.png"
        image.save(bond_path)
        crop = serial_crop(image)
        crop_path = out / f"strip_{index + 1:02d}_{serial}.png"
        crop.save(crop_path)
        manifest.append({
            "serial": serial,
            "denomination": denomination,
            "bengali": not args.english,
            "image": str(bond_path.relative_to(ROOT)),
            "strip": str(crop_path.relative_to(ROOT)),
        })

    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"Wrote {len(manifest)} samples to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
