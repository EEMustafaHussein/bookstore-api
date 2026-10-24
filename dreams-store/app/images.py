"""Saving uploaded photos: every file is decoded, resized and re-encoded as WebP."""

import io
import uuid

from PIL import Image, ImageOps, UnidentifiedImageError
from starlette.datastructures import UploadFile

from app.config import settings

Image.MAX_IMAGE_PIXELS = 50_000_000
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "GIF", "MPO", "AVIF"}


class ImageError(ValueError):
    pass


def uploaded_files(form, field: str) -> list[UploadFile]:
    """Files the browser actually sent for a field (an empty file input sends a blank part)."""
    return [
        item
        for item in form.getlist(field)
        if isinstance(item, UploadFile) and item.filename
    ]


def save_image(upload: UploadFile, folder: str, max_side: int = 1600) -> str:
    limit = settings.max_upload_mb * 1024 * 1024
    upload.file.seek(0)
    data = upload.file.read(limit + 1)
    if len(data) > limit:
        raise ImageError(f"الصورة «{upload.filename}» أكبر من {settings.max_upload_mb} ميغابايت")
    if not data:
        raise ImageError(f"الملف «{upload.filename}» فارغ")

    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()
            image_format = probe.format
        if image_format not in ALLOWED_FORMATS:
            raise ImageError(f"صيغة الملف «{upload.filename}» غير مدعومة")
        with Image.open(io.BytesIO(data)) as image:
            image = ImageOps.exif_transpose(image)
            has_alpha = image.mode in ("RGBA", "LA") or (
                image.mode == "P" and "transparency" in image.info
            )
            image = image.convert("RGBA" if has_alpha else "RGB")
            image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)

            name = f"{folder}/{uuid.uuid4().hex}.webp"
            target = settings.media_dir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            image.save(target, "WEBP", quality=84, method=4)
    except ImageError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError):
        raise ImageError(f"الملف «{upload.filename}» ليس صورة صالحة")
    return name


def delete_image(name: str | None) -> None:
    if not name:
        return
    root = settings.media_dir.resolve()
    target = (root / name).resolve()
    if root in target.parents and target.is_file():
        target.unlink(missing_ok=True)
