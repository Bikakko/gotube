"""Video library service for media assets, ownership, quota and sharing."""

from __future__ import annotations

import json
import logging
import secrets
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .db import MediaAsset, MediaSource, User, UserVideoItem
from .downloader import VIDEO_EXTENSIONS
from .media_fingerprint import fingerprint_file
from .quota import refresh_user_storage_usage, user_can_add_media

logger = logging.getLogger(__name__)


def normalize_source_url(url: str) -> str:
    """Normalize a source URL for reuse lookup without changing its semantics."""
    url = (url or "").strip()
    if not url:
        return ""
    try:
        parsed = urlparse(url)
    except Exception:
        return url
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or parsed.path
    return urlunparse((parsed.scheme.lower(), netloc, path, "", query, ""))


def source_platform(url: str) -> str:
    host = (urlparse(url).hostname or "").lower() if url else ""
    if "youtube.com" in host or "youtu.be" in host:
        return "YouTube"
    if "bilibili.com" in host or "b23.tv" in host:
        return "Bilibili"
    if "douyin.com" in host:
        return "Douyin"
    if "x.com" in host or "twitter.com" in host:
        return "Twitter/X"
    return host or ""


def register_completed_file(
    session: Session,
    *,
    owner_user_id: int,
    filepath: Path,
    download_dir: Path,
    source_url: str,
    title: str,
    file_hash: str,
    thumbnail: str = "",
    duration: float | None = None,
    meta: dict[str, Any] | None = None,
    created_from: str = "download",
) -> UserVideoItem:
    """Register a completed download and return the owning user's library item."""
    filepath = filepath.resolve()
    if not filepath.is_file():
        raise FileNotFoundError(str(filepath))

    owner = session.query(User).filter(User.id == owner_user_id).first()
    if not owner or not owner.is_active:
        raise ValueError("owner user is not active")

    fingerprint = fingerprint_file(filepath)
    asset = session.query(MediaAsset).filter(MediaAsset.fingerprint == fingerprint).first()
    now = datetime.now(UTC)

    if asset is None:
        if not user_can_add_media(session, owner, filepath.stat().st_size):
            raise ValueError("storage quota exceeded")
        asset = _create_media_asset(
            filepath=filepath,
            download_dir=download_dir,
            fingerprint=fingerprint,
            source_url=source_url,
            title=title,
            file_hash=file_hash,
            thumbnail=thumbnail,
            duration=duration,
            meta=meta,
            now=now,
        )
        session.add(asset)
        session.flush()
    else:
        existing_item = (
            session.query(UserVideoItem)
            .filter(
                UserVideoItem.owner_user_id == owner_user_id,
                UserVideoItem.media_asset_id == asset.id,
                UserVideoItem.deleted_at.is_(None),
            )
            .first()
        )
        if existing_item is not None:
            _ensure_media_source(session, asset, source_url)
            return existing_item
        if not user_can_add_media(session, owner, asset.size_bytes):
            raise ValueError("storage quota exceeded")
        asset.last_seen_at = now
        asset.source_url = asset.source_url or source_url or ""
        if title:
            asset.title = asset.title or title
        if Path(asset.filepath).resolve() != filepath:
            if Path(asset.filepath).is_file():
                _delete_duplicate_download(filepath, download_dir)
            else:
                asset.filepath = str(filepath)
                asset.filename = _relative_filename(filepath, download_dir)

    _ensure_media_source(session, asset, source_url)

    item = (
        session.query(UserVideoItem)
        .filter(
            UserVideoItem.owner_user_id == owner_user_id,
            UserVideoItem.media_asset_id == asset.id,
        )
        .first()
    )
    if item is None:
        item = UserVideoItem(
            owner_user_id=owner_user_id,
            media_asset_id=asset.id,
            display_title=title or asset.title or Path(asset.filepath).stem,
            share_token=_generate_share_token(session),
            share_enabled=True,
            created_from=created_from,
            saved_at=now,
        )
        session.add(item)
    else:
        item.deleted_at = None
        item.share_enabled = True
        item.display_title = title or item.display_title or asset.title
        item.saved_at = now
    session.flush()
    refresh_user_storage_usage(session, owner_user_id)
    session.flush()
    return item


def create_item_from_existing_source(
    session: Session,
    owner_user_id: int,
    source_url: str,
    *,
    created_from: str = "source_reuse",
) -> UserVideoItem | None:
    """Create a user item from a live media source without downloading again."""
    normalized = normalize_source_url(source_url)
    if not normalized:
        return None
    source = session.query(MediaSource).filter(MediaSource.normalized_url == normalized).first()
    if not source:
        return None
    asset = session.query(MediaAsset).filter(MediaAsset.id == source.media_asset_id).first()
    if not asset or not Path(asset.filepath).is_file():
        session.delete(source)
        session.flush()
        return None
    return register_completed_file(
        session,
        owner_user_id=owner_user_id,
        filepath=Path(asset.filepath),
        download_dir=_infer_download_dir(asset),
        source_url=source_url,
        title=asset.title,
        file_hash=asset.file_hash,
        thumbnail=asset.thumbnail,
        duration=asset.duration,
        meta=_load_meta_json(asset.meta_json),
        created_from=created_from,
    )


def list_user_video_items(session: Session, user: User, owner_user_id: int | None = None) -> list[dict[str, Any]]:
    """List visible user library items."""
    query = (
        session.query(UserVideoItem, MediaAsset, User)
        .join(MediaAsset, MediaAsset.id == UserVideoItem.media_asset_id)
        .join(User, User.id == UserVideoItem.owner_user_id)
        .filter(UserVideoItem.deleted_at.is_(None))
    )
    if user.role != "admin":
        query = query.filter(UserVideoItem.owner_user_id == user.id)
    elif owner_user_id is not None:
        query = query.filter(UserVideoItem.owner_user_id == owner_user_id)

    rows = []
    for item, asset, owner in query.order_by(UserVideoItem.saved_at.desc()).all():
        rows.append(_item_to_dict(item, asset, owner))
    return rows


def delete_user_video_item(
    session: Session,
    user: User,
    item_id: int,
    download_dir: Path,
) -> dict[str, Any]:
    """Delete one user's library item and remove media only after last reference."""
    item = session.query(UserVideoItem).filter(UserVideoItem.id == item_id).first()
    if not item or item.deleted_at is not None:
        raise HTTPException(status_code=404, detail="视频不存在")
    if user.role != "admin" and item.owner_user_id != user.id:
        raise HTTPException(status_code=403, detail="权限不足")

    asset = session.query(MediaAsset).filter(MediaAsset.id == item.media_asset_id).first()
    item.deleted_at = datetime.now(UTC)
    item.share_enabled = False
    session.flush()
    refresh_user_storage_usage(session, item.owner_user_id)

    active_refs = (
        session.query(UserVideoItem)
        .filter(
            UserVideoItem.media_asset_id == item.media_asset_id,
            UserVideoItem.deleted_at.is_(None),
        )
        .count()
    )
    deleted_files: list[str] = []
    physical_deleted = False
    if asset and active_refs == 0:
        deleted_files = _delete_media_files(asset, download_dir)
        session.query(MediaSource).filter(MediaSource.media_asset_id == asset.id).delete()
        session.delete(asset)
        physical_deleted = True
    session.flush()
    return {
        "status": "ok",
        "physical_deleted": physical_deleted,
        "deleted_files": deleted_files,
    }


def admin_delete_media_asset(
    session: Session,
    admin: User,
    media_asset_id: int,
    download_dir: Path,
) -> dict[str, Any]:
    """Maintenance delete: remove a media asset from disk and all user libraries."""
    if admin.role != "admin":
        raise HTTPException(status_code=403, detail="权限不足")

    asset = session.query(MediaAsset).filter(MediaAsset.id == media_asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="媒体不存在")

    items = session.query(UserVideoItem).filter(UserVideoItem.media_asset_id == asset.id).all()
    affected_users = {item.owner_user_id for item in items}
    for item in items:
        session.delete(item)

    deleted_files = _delete_media_files(asset, download_dir)
    session.query(MediaSource).filter(MediaSource.media_asset_id == asset.id).delete()
    session.delete(asset)
    session.flush()
    for user_id in affected_users:
        refresh_user_storage_usage(session, user_id)
    session.flush()
    return {
        "status": "ok",
        "affected_items": len(items),
        "affected_users": len(affected_users),
        "deleted_files": deleted_files,
    }


def resolve_share_token(session: Session, share_token: str) -> tuple[UserVideoItem, MediaAsset] | None:
    """Resolve an active share token to a live user item and media asset."""
    if not share_token:
        return None
    row = (
        session.query(UserVideoItem, MediaAsset, User)
        .join(MediaAsset, MediaAsset.id == UserVideoItem.media_asset_id)
        .join(User, User.id == UserVideoItem.owner_user_id)
        .filter(
            UserVideoItem.share_token == share_token,
            UserVideoItem.deleted_at.is_(None),
            UserVideoItem.share_enabled == True,
            User.is_active == True,
        )
        .first()
    )
    if not row:
        return None
    item, asset, _owner = row
    if not Path(asset.filepath).is_file():
        return None
    return item, asset


def _create_media_asset(
    *,
    filepath: Path,
    download_dir: Path,
    fingerprint: str,
    source_url: str,
    title: str,
    file_hash: str,
    thumbnail: str,
    duration: float | None,
    meta: dict[str, Any] | None,
    now: datetime,
) -> MediaAsset:
    return MediaAsset(
        fingerprint=fingerprint,
        file_hash=(file_hash or filepath.stem[:8]).lower(),
        filename=_relative_filename(filepath, download_dir),
        filepath=str(filepath),
        size_bytes=filepath.stat().st_size,
        title=title or filepath.stem,
        thumbnail=thumbnail or "",
        duration=duration,
        source_url=source_url or "",
        meta_json=json.dumps(meta or {}, ensure_ascii=False),
        created_at=now,
        last_seen_at=now,
    )


def _ensure_media_source(session: Session, asset: MediaAsset, source_url: str) -> None:
    normalized = normalize_source_url(source_url)
    if not normalized:
        return
    existing = session.query(MediaSource).filter(MediaSource.normalized_url == normalized).first()
    if existing:
        existing.media_asset_id = asset.id
        existing.last_seen_at = datetime.now(UTC)
        return
    session.add(
        MediaSource(
            media_asset_id=asset.id,
            source_url=source_url,
            normalized_url=normalized,
            platform=source_platform(source_url),
            platform_video_id="",
            created_at=datetime.now(UTC),
            last_seen_at=datetime.now(UTC),
        )
    )


def _generate_share_token(session: Session) -> str:
    while True:
        token = secrets.token_urlsafe(24)
        exists = session.query(UserVideoItem).filter(UserVideoItem.share_token == token).first()
        if not exists:
            return token


def _relative_filename(filepath: Path, download_dir: Path) -> str:
    try:
        return filepath.resolve().relative_to(download_dir.resolve()).as_posix()
    except ValueError:
        return filepath.name


def _infer_download_dir(asset: MediaAsset) -> Path:
    path = Path(asset.filepath).resolve()
    filename = Path(asset.filename)
    if len(filename.parts) > 1:
        return path.parents[len(filename.parts) - 1]
    return path.parent


def _load_meta_json(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw or "{}")
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _delete_duplicate_download(filepath: Path, download_dir: Path) -> None:
    if filepath.is_file():
        filepath.unlink()
    parent = filepath.parent
    if parent != download_dir and parent.exists():
        with suppress(OSError):
            if not any(parent.iterdir()):
                parent.rmdir()


def _delete_media_files(asset: MediaAsset, download_dir: Path) -> list[str]:
    deleted: list[str] = []
    video_path = Path(asset.filepath)
    parent = video_path.parent
    if video_path.is_file():
        video_path.unlink()
        deleted.append(_relative_filename(video_path, download_dir))
    if parent.is_dir():
        for child in list(parent.iterdir()):
            if child.is_file() and (child.name == "meta.json" or child.name.startswith("thumbnail")):
                child.unlink()
                deleted.append(_relative_filename(child, download_dir))
        if parent != download_dir:
            try:
                if not any(parent.iterdir()):
                    parent.rmdir()
                    deleted.append(_relative_filename(parent, download_dir) + "/")
            except OSError as exc:
                logger.warning("删除空媒体目录失败: %s, error=%s", parent, exc)
    return deleted


def _item_to_dict(item: UserVideoItem, asset: MediaAsset, owner: User) -> dict[str, Any]:
    return {
        "id": item.id,
        "owner_user_id": owner.id,
        "owner_username": owner.username,
        "media_asset_id": asset.id,
        "title": item.display_title or asset.title,
        "filename": asset.filename,
        "file_hash": asset.file_hash,
        "share_token": item.share_token,
        "share_enabled": item.share_enabled,
        "thumbnail": asset.thumbnail,
        "duration": asset.duration,
        "size": asset.size_bytes,
        "source_url": asset.source_url,
        "saved_at": item.saved_at.isoformat() if item.saved_at else None,
    }
