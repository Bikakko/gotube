"""Video library service for media assets, ownership, quota and sharing."""

from __future__ import annotations

import json
import logging
import secrets
from collections import defaultdict
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy import case, or_
from sqlalchemy.orm import Session

from .db import MediaAsset, MediaSource, User, UserVideoItem
from .downloader import VIDEO_EXTENSIONS
from .media_fingerprint import fingerprint_file
from .quota import refresh_user_storage_usage, user_can_add_media
from .url_normalizer import normalize_media_url

logger = logging.getLogger(__name__)

def normalize_source_url(url: str) -> str:
    """Normalize a source URL for reuse lookup without changing its semantics."""
    return normalize_media_url(url).canonical_url


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
            raise ValueError("视频库容量不足")
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
            raise ValueError("视频库容量不足")
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


def get_asset_from_existing_source(session: Session, source_url: str) -> MediaAsset | None:
    """Return a live media asset for an existing source URL without creating ownership."""
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
    return asset


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


def list_user_video_items_page(
    session: Session,
    user: User,
    *,
    owner_user_id: int | None = None,
    page: int = 1,
    per_page: int = 50,
) -> dict[str, Any]:
    """List visible user library items with pagination metadata."""
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

    per_page = max(1, min(int(per_page), 100))
    page = max(1, int(page))
    total = query.count()
    offset = (page - 1) * per_page
    rows = [
        _item_to_dict(item, asset, owner)
        for item, asset, owner in query.order_by(UserVideoItem.saved_at.desc()).offset(offset).limit(per_page).all()
    ]
    return {
        "videos": rows,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if per_page > 0 else 0,
    }


def list_admin_media_assets(
    session: Session,
    admin: User,
    *,
    owner_user_id: int | None = None,
    owner: str | None = None,
) -> list[dict[str, Any]]:
    """List global media assets once, with active owner references aggregated."""
    if admin.role != "admin":
        raise HTTPException(status_code=403, detail="权限不足")

    owner = (owner or "").strip().lower() or None
    query = session.query(MediaAsset)

    if owner_user_id is not None:
        query = (
            query.join(UserVideoItem, UserVideoItem.media_asset_id == MediaAsset.id)
            .filter(
                UserVideoItem.owner_user_id == owner_user_id,
                UserVideoItem.deleted_at.is_(None),
            )
            .distinct()
        )
    elif owner == "legacy":
        query = (
            query.outerjoin(
                UserVideoItem,
                (UserVideoItem.media_asset_id == MediaAsset.id) & (UserVideoItem.deleted_at.is_(None)),
            )
            .filter(UserVideoItem.id.is_(None))
            .distinct()
        )

    assets = query.order_by(MediaAsset.created_at.desc()).all()
    if not assets:
        return []

    asset_ids = [asset.id for asset in assets]
    owner_rows_by_asset: dict[int, list[tuple[UserVideoItem, User]]] = defaultdict(list)
    for item, owner_user in (
        session.query(UserVideoItem, User)
        .join(User, User.id == UserVideoItem.owner_user_id)
        .filter(
            UserVideoItem.media_asset_id.in_(asset_ids),
            UserVideoItem.deleted_at.is_(None),
        )
        .order_by(
            UserVideoItem.media_asset_id.asc(),
            UserVideoItem.saved_at.desc(),
            UserVideoItem.id.desc(),
        )
        .all()
    ):
        owner_rows_by_asset[item.media_asset_id].append((item, owner_user))

    source_rows_by_asset: dict[int, list[MediaSource]] = defaultdict(list)
    for source_row in (
        session.query(MediaSource)
        .filter(MediaSource.media_asset_id.in_(asset_ids))
        .order_by(MediaSource.media_asset_id.asc(), MediaSource.created_at.asc(), MediaSource.id.asc())
        .all()
    ):
        source_rows_by_asset[source_row.media_asset_id].append(source_row)

    return [
        _admin_media_asset_to_dict(
            asset,
            owner_rows_by_asset.get(asset.id, []),
            source_rows_by_asset.get(asset.id, []),
        )
        for asset in assets
    ]


_SOURCE_PATTERNS: dict[str, tuple[str, ...]] = {
    "YouTube": ("youtube.com", "youtu.be"),
    "Bilibili": ("bilibili.com", "b23.tv"),
    "Twitter/X": ("twitter.com", "x.com"),
    "Douyin": ("douyin.com",),
    "AcFun": ("acfun.cn",),
    "爱奇艺": ("iqiyi.com",),
    "优酷": ("youku.com",),
    "腾讯视频": ("qq.com",),
    "快手": ("kuaishou.com",),
}


def _source_pattern_filter(patterns: tuple[str, ...]):
    return or_(*[MediaAsset.source_url.ilike(f"%{pattern}%") for pattern in patterns])


def _list_available_source_platforms(query) -> list[str]:
    platform_case = case(
        *[
            (_source_pattern_filter(patterns), label)
            for label, patterns in _SOURCE_PATTERNS.items()
        ],
        else_=None,
    ).label("platform")
    rows = (
        query.order_by(None)
        .with_entities(platform_case)
        .filter(MediaAsset.source_url.is_not(None))
        .distinct()
        .all()
    )
    return sorted([row[0] for row in rows if row[0]])


def list_admin_media_assets_page(
    session: Session,
    admin: User,
    *,
    owner_user_id: int | None = None,
    owner: str | None = None,
    keyword: str | None = None,
    source: str | None = None,
    time_filter: str | None = "all",
    page: int = 1,
    per_page: int = 20,
) -> dict[str, Any]:
    """List admin media assets from the database with filters and pagination."""
    if admin.role != "admin":
        raise HTTPException(status_code=403, detail="权限不足")

    owner = (owner or "").strip().lower() or None
    keyword = (keyword or "").strip()
    source = (source or "").strip()
    time_filter = (time_filter or "all").strip().lower()
    page = max(1, int(page))
    per_page = max(1, min(int(per_page), 100))

    query = session.query(MediaAsset)
    if owner_user_id is not None:
        query = (
            query.join(UserVideoItem, UserVideoItem.media_asset_id == MediaAsset.id)
            .filter(
                UserVideoItem.owner_user_id == owner_user_id,
                UserVideoItem.deleted_at.is_(None),
            )
            .distinct()
        )
    elif owner == "legacy":
        query = (
            query.outerjoin(
                UserVideoItem,
                (UserVideoItem.media_asset_id == MediaAsset.id) & (UserVideoItem.deleted_at.is_(None)),
            )
            .filter(UserVideoItem.id.is_(None))
            .distinct()
        )

    if keyword:
        query = query.filter(MediaAsset.title.ilike(f"%{keyword}%"))

    if source:
        patterns = _SOURCE_PATTERNS.get(source)
        if patterns:
            query = query.filter(_source_pattern_filter(patterns))
        else:
            query = query.filter(MediaAsset.source_url.ilike(f"%{source}%"))

    local_tz = UTC
    now = datetime.now(local_tz)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if time_filter == "today":
        query = query.filter(MediaAsset.created_at >= today_start)
    elif time_filter == "week":
        query = query.filter(MediaAsset.created_at >= week_start)
    elif time_filter == "month":
        query = query.filter(MediaAsset.created_at >= month_start)
    elif time_filter == "earlier":
        query = query.filter(MediaAsset.created_at < month_start)

    total = query.count()
    asset_query = query.order_by(MediaAsset.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    assets = asset_query.all()
    if not assets:
        return {
            "videos": [],
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page if per_page > 0 else 0,
            "all_sources": [],
        }

    asset_ids = [asset.id for asset in assets]
    owner_rows_by_asset: dict[int, list[tuple[UserVideoItem, User]]] = defaultdict(list)
    for item, owner_user in (
        session.query(UserVideoItem, User)
        .join(User, User.id == UserVideoItem.owner_user_id)
        .filter(
            UserVideoItem.media_asset_id.in_(asset_ids),
            UserVideoItem.deleted_at.is_(None),
        )
        .order_by(
            UserVideoItem.media_asset_id.asc(),
            UserVideoItem.saved_at.desc(),
            UserVideoItem.id.desc(),
        )
        .all()
    ):
        owner_rows_by_asset[item.media_asset_id].append((item, owner_user))

    source_rows_by_asset: dict[int, list[MediaSource]] = defaultdict(list)
    for source_row in (
        session.query(MediaSource)
        .filter(MediaSource.media_asset_id.in_(asset_ids))
        .order_by(MediaSource.media_asset_id.asc(), MediaSource.created_at.asc(), MediaSource.id.asc())
        .all()
    ):
        source_rows_by_asset[source_row.media_asset_id].append(source_row)

    all_sources = _list_available_source_platforms(query)

    videos = [
        _admin_media_asset_to_dict(
            asset,
            owner_rows_by_asset.get(asset.id, []),
            source_rows_by_asset.get(asset.id, []),
        )
        for asset in assets
    ]

    # 将本地缩略图路径转换为 API URL
    for video in videos:
        thumbnail = video.get("thumbnail") or ""
        if thumbnail and not thumbnail.startswith(("http://", "https://")):
            video["thumbnail"] = f"/api/thumbnail/{video.get('file_hash', '')}"

    return {
        "videos": videos,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if per_page > 0 else 0,
        "all_sources": all_sources,
    }


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
    if item.owner_user_id != user.id:
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


def set_user_video_share_enabled(
    session: Session,
    user: User,
    item_id: int,
    share_enabled: bool,
) -> dict[str, Any]:
    """Enable or disable sharing for one visible user library item."""
    item, asset = _get_visible_item_asset(session, user, item_id)
    item.share_enabled = share_enabled
    session.flush()
    return _item_to_dict(item, asset, user)


def get_user_video_asset_for_download(
    session: Session,
    user: User,
    item_id: int,
) -> tuple[UserVideoItem, MediaAsset]:
    """Resolve one visible user library item to a live media asset for download."""
    return _get_visible_item_asset(session, user, item_id, require_file=True)


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


def _get_visible_item_asset(
    session: Session,
    user: User,
    item_id: int,
    *,
    require_file: bool = False,
) -> tuple[UserVideoItem, MediaAsset]:
    row = (
        session.query(UserVideoItem, MediaAsset)
        .join(MediaAsset, MediaAsset.id == UserVideoItem.media_asset_id)
        .filter(
            UserVideoItem.id == item_id,
            UserVideoItem.deleted_at.is_(None),
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="视频不存在")
    item, asset = row
    if item.owner_user_id != user.id:
        raise HTTPException(status_code=403, detail="权限不足")
    if require_file and not Path(asset.filepath).is_file():
        raise HTTPException(status_code=404, detail="视频文件不存在")
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
        "thumbnail_url": f"/api/me/videos/{item.id}/thumbnail" if asset.thumbnail else "",
        "duration": asset.duration,
        "size": asset.size_bytes,
        "source_url": asset.source_url,
        "saved_at": item.saved_at.isoformat() if item.saved_at else None,
    }


def _admin_media_asset_to_dict(
    asset: MediaAsset,
    owner_rows: list[tuple[UserVideoItem, User]],
    source_rows: list[MediaSource],
) -> dict[str, Any]:
    owners = [
        {
            "item_id": item.id,
            "user_id": owner.id,
            "username": owner.username,
            "share_enabled": item.share_enabled,
            "share_token": item.share_token,
            "saved_at": item.saved_at.isoformat() if item.saved_at else None,
            "display_title": item.display_title or asset.title,
        }
        for item, owner in owner_rows
    ]
    owner_count = len(owners)
    first_owner = owners[0] if owners else None
    first_enabled_share = next((owner for owner in owners if owner.get("share_enabled")), first_owner)
    source_urls = [row.source_url for row in source_rows if row.source_url]
    source_count = len(source_urls)
    source_url = asset.source_url or ""

    if owner_count == 0:
        owner_username = "未归属"
    elif owner_count == 1:
        owner_username = str(first_owner["username"])
    else:
        owner_username = f"{owner_count} 个用户"

    return {
        "id": f"media-{asset.id}",
        "item_id": first_owner["item_id"] if first_owner else None,
        "owner_user_id": first_owner["user_id"] if first_owner else None,
        "owner_username": owner_username,
        "owners": owners,
        "owner_count": owner_count,
        "media_asset_id": asset.id,
        "title": asset.title,
        "filename": asset.filename,
        "filepath": asset.filepath,
        "file_hash": asset.file_hash,
        "share_token": first_enabled_share["share_token"] if first_enabled_share else "",
        "share_enabled": bool(first_enabled_share and first_enabled_share.get("share_enabled")),
        "thumbnail": asset.thumbnail,
        "thumbnail_url": f"/api/thumbnail/{asset.file_hash}" if asset.thumbnail else "",
        "video_id": "",
        "duration": asset.duration or 0,
        "size": asset.size_bytes,
        "source_url": source_url,
        "source_urls": source_urls,
        "url": source_url,
        "source": source_platform(source_url),
        "created_at": asset.created_at.isoformat() if asset.created_at else datetime.now(UTC).isoformat(),
        "saved_at": first_owner["saved_at"] if first_owner else None,
        "tags": [],
        "reference_count": owner_count,
        "source_count": source_count,
        "is_legacy": owner_count == 0,
    }
