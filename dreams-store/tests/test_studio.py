from PIL import Image, ImageDraw, ImageStat

from tools import studio


def test_light_correction_keeps_true_colours():
    navy = Image.new("RGB", (400, 500), (28, 34, 70))
    corrected = studio.gentle_levels(navy)
    assert ImageStat.Stat(corrected).mean == ImageStat.Stat(navy).mean  # a dark piece stays dark

    # A yellowish, dim photo of a blue piece on a white sheet comes back to its real colour.
    photo = Image.new("RGB", (400, 500), (190, 177, 150))
    ImageDraw.Draw(photo).rectangle((120, 120, 280, 400), fill=(78, 97, 109))
    alpha = Image.new("L", photo.size, 0)
    ImageDraw.Draw(alpha).rectangle((120, 120, 280, 400), fill=255)
    fixed = studio.correct_light(photo, studio.backdrop_reference(photo, alpha))
    r, g, b = fixed.getpixel((200, 260))
    assert b > g > r and abs(r - 96) < 20 and abs(b - 170) < 25


def test_close_up_keeps_its_background(tmp_path):
    source = tmp_path / "label.jpg"
    Image.new("RGB", (900, 700), (120, 90, 80)).save(source)
    target, note = studio.process(source, tmp_path / "out", None, keep_background=True, mark=True)
    with Image.open(target) as result:
        assert result.size == (studio.WIDTH, studio.HEIGHT)
    assert note == "kept background"
