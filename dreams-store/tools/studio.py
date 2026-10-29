"""Turns phone photos of clothes into clean, matching shop photos.

    pip install -r tools/requirements-studio.txt
    python tools/studio.py photos/*.jpg --out ready/
    python tools/studio.py label.jpg --keep-background     # close-ups: fabric, labels, flaws

Each piece is cut out, its light evened out, set on a soft studio background with a
gentle shadow, and saved at 1200x1500 (the shop's 4:5 frame) with a small shop mark.

Colours stay true to the piece: only exposure, contrast and the white balance read from
the sheet behind it are adjusted. Nothing on the garment itself (stains, wear, colour)
is painted over, so bala pieces are shown as they really are.
"""

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageStat

WIDTH, HEIGHT = 1200, 1500
FONT = Path(__file__).resolve().parent / "fonts" / "ArefRuqaa-Bold.ttf"
MARK_TEXT = "ملابس الأحلام"
INK = (59, 42, 31)


def load(path: Path) -> Image.Image:
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
    image.thumbnail((2400, 2400), Image.Resampling.LANCZOS)
    return image


def backdrop_reference(photo: Image.Image, alpha: Image.Image) -> tuple[float, float, float] | None:
    """Mean colour of the bright part of the backdrop, when it is a white or grey sheet."""
    small = photo.resize((300, round(300 * photo.height / photo.width)))
    mask = alpha.resize(small.size).point(lambda a: 255 if a < 16 else 0)
    luminance = small.convert("L")
    stat = ImageStat.Stat(luminance, mask)
    if not stat.count[0] or stat.count[0] < 0.08 * small.width * small.height:
        return None
    bright = ImageChops.multiply(mask, luminance.point(lambda v: 255 if v >= stat.median[0] else 0))
    r, g, b = ImageStat.Stat(small, bright).mean
    if min(r, g, b) < 70 or min(r, g, b) / max(r, g, b) < 0.72:
        return None  # dark or coloured backdrop: it says nothing about the light
    return r, g, b


def gentle_levels(photo: Image.Image) -> Image.Image:
    """Brightens a dim photo a little without touching its colours or its dark tones.

    A full auto-contrast would stretch a navy dress into royal blue. Here only the bright
    end is pulled up toward white, by a fifth at most, and a photo with no bright part at
    all (dark fabric filling the frame) is left as it is.
    """
    histogram = photo.convert("L").histogram()
    cut = sum(histogram) * 0.005
    high = next(v for v in range(255, -1, -1) if sum(histogram[v:]) > cut)
    if high < 160:
        return photo
    scale = 255 / max(high, 215)
    return photo.point(lambda v: min(255, round(v * scale)))


def correct_light(photo: Image.Image, reference: tuple[float, float, float] | None) -> Image.Image:
    if reference is None:
        return gentle_levels(photo)
    grey = sum(reference) / 3
    # The sheet should read as a clean white: fix the colour cast, then the exposure.
    # Its known colour is the only guide, so the piece keeps its own colours and depth.
    gains = [min(max(grey / channel, 0.85), 1.2) for channel in reference]
    exposure = min(max(238 / grey, 0.9), 1.5)
    channels = [
        band.point(lambda v, k=gain * exposure: min(255, round(v * k)))
        for band, gain in zip(photo.split(), gains)
    ]
    return Image.merge("RGB", channels)


def studio_background() -> Image.Image:
    top, bottom = (252, 249, 245), (240, 233, 225)
    gradient = Image.linear_gradient("L").resize((WIDTH, HEIGHT))
    background = Image.composite(Image.new("RGB", (WIDTH, HEIGHT), bottom), Image.new("RGB", (WIDTH, HEIGHT), top), gradient)
    glow = Image.new("L", (WIDTH, HEIGHT), 0)
    ImageDraw.Draw(glow).ellipse((WIDTH * 0.12, HEIGHT * 0.1, WIDTH * 0.88, HEIGHT * 0.78), fill=150)
    glow = glow.filter(ImageFilter.GaussianBlur(160))
    return Image.composite(Image.new("RGB", (WIDTH, HEIGHT), (255, 255, 255)), background, glow)


def place_on_studio(piece: Image.Image) -> Image.Image:
    box = piece.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    piece = piece.crop(box)
    scale = min(WIDTH * 0.78 / piece.width, HEIGHT * 0.84 / piece.height)
    piece = piece.resize((max(1, round(piece.width * scale)), max(1, round(piece.height * scale))), Image.Resampling.LANCZOS)
    left = (WIDTH - piece.width) // 2
    top = round(HEIGHT * 0.49 - piece.height / 2)

    canvas = studio_background()
    shadow_mask = Image.new("L", (WIDTH, HEIGHT), 0)
    shadow_mask.paste(piece.getchannel("A").point(lambda a: a * 0.22), (left + 6, top + 22))
    shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(26))
    canvas = Image.composite(Image.new("RGB", (WIDTH, HEIGHT), (58, 42, 32)), canvas, shadow_mask)
    canvas.paste(piece, (left, top), piece)
    return canvas


def fill_frame(photo: Image.Image) -> Image.Image:
    return ImageOps.fit(photo, (WIDTH, HEIGHT), Image.Resampling.LANCZOS, centering=(0.5, 0.45))


def add_mark(canvas: Image.Image, light: bool) -> Image.Image:
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    colour = (255, 255, 255, 150) if light else (*INK, 90)
    font = ImageFont.truetype(str(FONT), 40)
    text_box = draw.textbbox((0, 0), MARK_TEXT, font=font, direction="rtl", language="ar")
    x, y = 44, HEIGHT - 44 - (text_box[3] - text_box[1])
    draw.text((x - text_box[0], y - text_box[1]), MARK_TEXT, font=font, fill=colour, direction="rtl", language="ar")
    # A small crescent before the name, like the shop logo.
    moon_x, moon_y, r = x + (text_box[2] - text_box[0]) + 30, y + (text_box[3] - text_box[1]) / 2, 14
    draw.ellipse((moon_x - r, moon_y - r, moon_x + r, moon_y + r), fill=colour)
    draw.ellipse((moon_x - r + 9, moon_y - r - 4, moon_x + r + 9, moon_y + r - 4), fill=(0, 0, 0, 0))
    return Image.alpha_composite(canvas.convert("RGBA"), layer).convert("RGB")


def finish(image: Image.Image) -> Image.Image:
    return image.filter(ImageFilter.UnsharpMask(radius=1.6, percent=55, threshold=3))


def process(path: Path, out_dir: Path, session, keep_background: bool, mark: bool) -> tuple[Path, str]:
    photo = load(path)
    note = "cut out"
    if keep_background:
        result = fill_frame(gentle_levels(photo))
        note = "kept background"
    else:
        from rembg import remove

        cutout = remove(photo, session=session, post_process_mask=True)
        alpha = cutout.getchannel("A")
        coverage = ImageStat.Stat(alpha).mean[0] / 255
        if not 0.03 < coverage < 0.97:
            # The model could not tell the piece from its background: keep the photo as it is.
            result = fill_frame(gentle_levels(photo))
            note = "kept background (could not separate the piece)"
        else:
            corrected = correct_light(photo, backdrop_reference(photo, alpha))
            piece = corrected.convert("RGBA")
            piece.putalpha(alpha)
            result = place_on_studio(piece)
    result = finish(result)
    if mark:
        result = add_mark(result, light=keep_background and ImageStat.Stat(result.convert("L")).mean[0] < 110)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{path.stem}-studio.jpg"
    result.save(target, "JPEG", quality=92, optimize=True, progressive=True)
    return target, note


def main() -> int:
    parser = argparse.ArgumentParser(description="Make shop-ready photos of clothes")
    parser.add_argument("photos", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, default=Path("ready"))
    parser.add_argument("--keep-background", action="store_true", help="for close-ups of fabric, labels or flaws")
    parser.add_argument("--no-mark", action="store_true", help="leave out the shop name in the corner")
    args = parser.parse_args()

    session = None
    if not args.keep_background:
        from rembg import new_session

        session = new_session("isnet-general-use")
    for path in args.photos:
        target, note = process(path, args.out, session, args.keep_background, not args.no_mark)
        print(f"{path.name} -> {target} ({note})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
