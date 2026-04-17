"""Filesystem path safety helpers."""

from pathlib import Path

from fastapi import HTTPException


def resolve_inside(base_dir: Path, *parts: str | Path) -> Path:
    """Resolve a path and ensure it remains inside base_dir."""
    base = base_dir.resolve()
    target = base.joinpath(*parts).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="非法文件路径") from exc
    return target
