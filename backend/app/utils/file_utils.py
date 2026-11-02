"""utils/file_utils.py -- upload validation. Never trusts the client
filename or content-type: the bytes are opened with Pillow to confirm they
are really a JPEG/PNG/WEBP. Files are stored under uploads/<subdir>/ with a
server-generated name."""
import io
import os
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "uploads"))
SUBDIRS = ("reports", "before", "after")
for _d in SUBDIRS:
    (UPLOAD_DIR / _d).mkdir(parents=True, exist_ok=True)

_EXT = {"jpeg": ".jpg", "png": ".png", "webp": ".webp"}


def save_upload(file: UploadFile, settings: dict | None = None, subdir: str = "reports") -> str:
    from ..config import get_settings
    settings = settings or get_settings()
    if file is None:
        raise HTTPException(status_code=400, detail="Image is required.")
    if subdir not in SUBDIRS:
        raise HTTPException(status_code=400, detail="Invalid upload folder.")
    max_bytes = int(float(settings["max_image_mb"]) * 1024 * 1024)
    contents = file.file.read(max_bytes + 1)
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Image is required.")
    if len(contents) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Image exceeds {settings['max_image_mb']} MB limit.")
    try:
        with Image.open(io.BytesIO(contents)) as im:
            im.verify()
            fmt = (im.format or "").lower()
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise HTTPException(status_code=400, detail="Unsupported or corrupt image. Use JPEG, PNG or WEBP.")
    if fmt not in settings["allowed_image_types"] or fmt not in _EXT:
        raise HTTPException(status_code=400, detail="Unsupported image format. Use JPEG, PNG or WEBP.")
    dest = UPLOAD_DIR / subdir / f"{uuid.uuid4().hex}{_EXT[fmt]}"
    dest.write_bytes(contents)
    return to_stored(dest)


def to_stored(physical: Path) -> str:
    """What goes in the database: always 'uploads/<subdir>/<file>' -- the URL path under the /uploads static
    mount, independent of where UPLOAD_DIR physically lives (relative, absolute, Docker volume...)."""
    return "uploads/" + Path(physical).relative_to(UPLOAD_DIR).as_posix()


def physical_path(stored: str) -> str:
    """Resolve a stored path back to the file on disk. Also accepts legacy rows that stored a filesystem path."""
    if stored.startswith("uploads/"):
        return str(UPLOAD_DIR / stored[len("uploads/"):])
    return stored
