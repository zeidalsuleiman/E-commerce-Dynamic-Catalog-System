"""Image upload handling: validation, storage, and cleanup.

Files are stored on disk under app/static/uploads/products/{product_id}/
and referenced from product_image.file_path. The database never holds
image bytes.
"""
import uuid
from pathlib import Path

from PIL import Image

UPLOAD_ROOT = Path("app/static/uploads/products")
MAX_BYTES = 5 * 1024 * 1024          # 5 MB
MAX_DIMENSION = 2000                  # px, longest side
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
EXTENSION = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}


class UploadError(Exception):
    pass


def save_image(product_id, upload_file, sort_order=0):
    """Validate and store one uploaded image. Returns a metadata dict."""
    raw = upload_file.file.read()

    if len(raw) > MAX_BYTES:
        raise UploadError(
            f"{upload_file.filename} is larger than "
            f"{MAX_BYTES // (1024*1024)} MB."
        )
    if not raw:
        raise UploadError(f"{upload_file.filename} is empty.")

    # Verify by content, not by filename. A .jpg can contain anything.
    upload_file.file.seek(0)
    try:
        img = Image.open(upload_file.file)
        img.verify()
    except (OSError, ValueError):
        raise UploadError(f"{upload_file.filename} is not a valid image.")

    upload_file.file.seek(0)
    img = Image.open(upload_file.file)

    if img.format not in ALLOWED_FORMATS:
        raise UploadError(
            f"{upload_file.filename}: only JPEG, PNG and WEBP are accepted."
        )

    if max(img.size) > MAX_DIMENSION:
        img.thumbnail((MAX_DIMENSION, MAX_DIMENSION))

    # Generated filename — never trust the user's.
    fmt = img.format
    filename = f"{uuid.uuid4().hex}{EXTENSION[fmt]}"
    folder = UPLOAD_ROOT / str(product_id)
    folder.mkdir(parents=True, exist_ok=True)

    full_path = folder / filename
    if fmt == "JPEG":
        img.convert("RGB").save(full_path, "JPEG", quality=85, optimize=True)
    else:
        img.save(full_path, fmt, optimize=True)

    return {
        "file_path": f"products/{product_id}/{filename}",
        "width": img.width,
        "height": img.height,
        "file_size": full_path.stat().st_size,
        "sort_order": sort_order,
        "is_primary": 1 if sort_order == 0 else 0,
    }


def delete_image_file(file_path):
    """Remove a file from disk. Silent if already gone."""
    full = Path("app/static/uploads") / file_path
    try:
        full.unlink()
    except FileNotFoundError:
        pass


def delete_product_folder(product_id):
    """Remove a product's entire image folder."""
    folder = UPLOAD_ROOT / str(product_id)
    if folder.exists():
        for f in folder.iterdir():
            f.unlink()
        folder.rmdir()