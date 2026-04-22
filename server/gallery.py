"""Read-only public gallery helpers."""

import re
from pathlib import Path

from fastapi import HTTPException

from .config import settings
from .path_utils import resolve_inside

GALLERY_DIR = settings.project_root / "gallery"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}
SAFE_SLUG_RE = re.compile(r"^[a-zA-Z0-9_-]{1,80}$")
SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9._-]{1,255}$")


def _raise_not_found() -> None:
    raise HTTPException(status_code=404, detail="资源不存在")


def _validate_slug(slug: str) -> str:
    if not slug or not SAFE_SLUG_RE.fullmatch(slug):
        _raise_not_found()
    return slug


def _validate_name(name: str) -> str:
    if not name or not SAFE_NAME_RE.fullmatch(name):
        _raise_not_found()
    return name


def _ensure_gallery_root(base_dir: Path | None = None) -> Path:
    root = (base_dir or GALLERY_DIR).resolve()
    if not root.exists():
        return root
    if not root.is_dir():
        _raise_not_found()
    return root


def _list_image_files(album_dir: Path) -> list[Path]:
    return sorted(
        [
            file
            for file in album_dir.iterdir()
            if file.is_file() and file.suffix.lower() in IMAGE_EXTENSIONS
        ],
        key=lambda item: item.name.lower(),
    )


def list_albums(base_dir: Path | None = None) -> list[dict]:
    root = _ensure_gallery_root(base_dir)
    if not root.exists():
        return []

    albums = []
    for entry in sorted([p for p in root.iterdir() if p.is_dir()], key=lambda item: item.name.lower()):
        images = _list_image_files(entry)
        if not images:
            continue
        cover = images[0]
        albums.append(
            {
                "slug": entry.name,
                "title": entry.name,
                "cover_name": cover.name,
                "image_count": len(images),
            }
        )
    return albums


def get_album(base_dir: Path | None, slug: str) -> dict:
    root = _ensure_gallery_root(base_dir)
    slug = _validate_slug(slug)
    album_dir = resolve_inside(root, slug)
    if not album_dir.is_dir():
        _raise_not_found()

    images = _list_image_files(album_dir)
    if not images:
        _raise_not_found()

    return {
        "slug": slug,
        "title": slug,
        "images": [{"name": image.name} for image in images],
    }


def resolve_image_path(base_dir: Path | None, slug: str, name: str) -> Path:
    root = _ensure_gallery_root(base_dir)
    slug = _validate_slug(slug)
    name = _validate_name(name)
    image_path = resolve_inside(root, slug, name)
    if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_EXTENSIONS:
        _raise_not_found()
    return image_path
