"""Database migrations for lightweight SQLite deployments."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, inspect, text

from .downloader import VIDEO_EXTENSIONS
from .media_fingerprint import fingerprint_file
from .video_library import normalize_source_url, source_platform

logger = logging.getLogger(__name__)

V4_SCHEMA_VERSION = 4
SKIP_DIR_NAMES = {"temp_guest", ".temp_ytdlp", "__pycache__"}


def run_v4_migrations(engine: Engine, download_dir: Path) -> None:
    """Apply v4 schema migrations and index legacy videos once."""
    with engine.begin() as conn:
        _ensure_schema(engine, conn)
        _backfill_media_sources(conn)
        if _migration_exists(conn, V4_SCHEMA_VERSION):
            return

        _migrate_readonly_users(conn)
        indexed_count = _index_legacy_media_assets(conn, download_dir)
        conn.execute(
            text(
                """
                INSERT INTO schema_migrations (version, name, applied_at)
                VALUES (:version, :name, :applied_at)
                """
            ),
            {
                "version": V4_SCHEMA_VERSION,
                "name": "v4_media_assets_and_invites",
                "applied_at": _utcnow(),
            },
        )
        logger.info("v4 数据库迁移完成，登记 legacy 视频 %d 个", indexed_count)


def _ensure_schema(engine: Engine, conn) -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    if "users" in tables:
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        if "storage_quota_mb" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN storage_quota_mb INTEGER"))
        if "storage_used_bytes" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN storage_used_bytes INTEGER NOT NULL DEFAULT 0"))

    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version INTEGER NOT NULL UNIQUE,
                name VARCHAR(100) NOT NULL,
                applied_at DATETIME NOT NULL
            )
            """
        )
    )
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_schema_migrations_version ON schema_migrations (version)"))

    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS media_assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fingerprint VARCHAR(64) NOT NULL UNIQUE,
                file_hash VARCHAR(32) NOT NULL,
                filename TEXT NOT NULL,
                filepath TEXT NOT NULL,
                size_bytes INTEGER NOT NULL DEFAULT 0,
                title TEXT NOT NULL DEFAULT '',
                thumbnail TEXT NOT NULL DEFAULT '',
                duration REAL,
                source_url TEXT NOT NULL DEFAULT '',
                meta_json TEXT NOT NULL DEFAULT '{}',
                created_at DATETIME NOT NULL,
                last_seen_at DATETIME NOT NULL
            )
            """
        )
    )
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_media_assets_fingerprint ON media_assets (fingerprint)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_media_assets_file_hash ON media_assets (file_hash)"))

    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS media_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                media_asset_id INTEGER NOT NULL,
                source_url TEXT NOT NULL DEFAULT '',
                normalized_url TEXT NOT NULL,
                platform VARCHAR(50) NOT NULL DEFAULT '',
                platform_video_id VARCHAR(128) NOT NULL DEFAULT '',
                created_at DATETIME NOT NULL,
                last_seen_at DATETIME NOT NULL,
                FOREIGN KEY(media_asset_id) REFERENCES media_assets (id),
                CONSTRAINT uq_media_source_normalized_url UNIQUE (normalized_url)
            )
            """
        )
    )
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_media_sources_media_asset_id ON media_sources (media_asset_id)"))

    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS user_video_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_user_id INTEGER NOT NULL,
                media_asset_id INTEGER NOT NULL,
                display_title TEXT NOT NULL DEFAULT '',
                share_token VARCHAR(64) NOT NULL UNIQUE,
                share_enabled BOOLEAN NOT NULL DEFAULT 1,
                created_from VARCHAR(32) NOT NULL DEFAULT 'download',
                saved_at DATETIME NOT NULL,
                deleted_at DATETIME,
                FOREIGN KEY(owner_user_id) REFERENCES users (id),
                FOREIGN KEY(media_asset_id) REFERENCES media_assets (id),
                CONSTRAINT uq_user_video_item_owner_media UNIQUE (owner_user_id, media_asset_id)
            )
            """
        )
    )
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_user_video_items_owner_user_id ON user_video_items (owner_user_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_user_video_items_media_asset_id ON user_video_items (media_asset_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_user_video_items_deleted_at ON user_video_items (deleted_at)"))

    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS invite_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code_hash VARCHAR(128) NOT NULL UNIQUE,
                created_by_user_id INTEGER NOT NULL,
                max_uses INTEGER NOT NULL DEFAULT 1,
                used_count INTEGER NOT NULL DEFAULT 0,
                expires_at DATETIME,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL,
                FOREIGN KEY(created_by_user_id) REFERENCES users (id)
            )
            """
        )
    )
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_invite_codes_code_hash ON invite_codes (code_hash)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_invite_codes_created_by_user_id ON invite_codes (created_by_user_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_invite_codes_is_active ON invite_codes (is_active)"))


def _migration_exists(conn, version: int) -> bool:
    row = conn.execute(
        text("SELECT 1 FROM schema_migrations WHERE version = :version"),
        {"version": version},
    ).first()
    return row is not None


def _migrate_readonly_users(conn) -> None:
    conn.execute(text("UPDATE users SET role = 'user' WHERE role = 'readonly'"))


def _backfill_media_sources(conn) -> int:
    rows = conn.execute(
        text(
            """
            SELECT id, fingerprint, source_url, created_at, last_seen_at
            FROM media_assets
            WHERE source_url IS NOT NULL AND source_url != ''
            """
        )
    ).all()
    count = 0
    for row in rows:
        normalized = normalize_source_url(row.source_url)
        if not normalized:
            continue
        result = conn.execute(
            text(
                """
                INSERT OR IGNORE INTO media_sources (
                    media_asset_id, source_url, normalized_url, platform,
                    platform_video_id, created_at, last_seen_at
                )
                VALUES (
                    :media_asset_id, :source_url, :normalized_url, :platform,
                    '', :created_at, :last_seen_at
                )
                """
            ),
            {
                "media_asset_id": row.id,
                "source_url": row.source_url,
                "normalized_url": normalized,
                "platform": source_platform(row.source_url),
                "created_at": row.created_at,
                "last_seen_at": row.last_seen_at,
            },
        )
        count += result.rowcount or 0
    return count


def _index_legacy_media_assets(conn, download_dir: Path) -> int:
    if not download_dir.exists():
        return 0

    indexed_count = 0
    for video_file in sorted(download_dir.rglob("*")):
        if not _is_indexable_video(download_dir, video_file):
            continue

        try:
            media = _build_media_record(download_dir, video_file)
            conn.execute(
                text(
                    """
                    INSERT OR IGNORE INTO media_assets (
                        fingerprint, file_hash, filename, filepath, size_bytes, title,
                        thumbnail, duration, source_url, meta_json, created_at, last_seen_at
                    )
                    VALUES (
                        :fingerprint, :file_hash, :filename, :filepath, :size_bytes, :title,
                        :thumbnail, :duration, :source_url, :meta_json, :created_at, :last_seen_at
                    )
                    """
                ),
                media,
            )
            if media["source_url"]:
                conn.execute(
                    text(
                        """
                        INSERT OR IGNORE INTO media_sources (
                            media_asset_id, source_url, normalized_url, platform,
                            platform_video_id, created_at, last_seen_at
                        )
                        SELECT id, :source_url, :normalized_url, :platform,
                               '', :created_at, :last_seen_at
                        FROM media_assets
                        WHERE fingerprint = :fingerprint
                        """
                    ),
                    {
                        "fingerprint": media["fingerprint"],
                        "source_url": media["source_url"],
                        "normalized_url": normalize_source_url(media["source_url"]),
                        "platform": source_platform(media["source_url"]),
                        "created_at": media["created_at"],
                        "last_seen_at": media["last_seen_at"],
                    },
                )
            indexed_count += 1
        except Exception as exc:
            logger.warning("登记 legacy 视频失败: %s, error=%s", video_file, exc)

    return indexed_count


def _is_indexable_video(download_dir: Path, path: Path) -> bool:
    if not path.is_file() or path.is_symlink() or path.suffix.lower() not in VIDEO_EXTENSIONS:
        return False
    relative_parts = path.resolve().relative_to(download_dir.resolve()).parts
    return not any(part in SKIP_DIR_NAMES for part in relative_parts)


def _build_media_record(download_dir: Path, video_file: Path) -> dict[str, Any]:
    meta = _read_meta(video_file.parent / "meta.json")
    file_hash = str(meta.get("file_hash") or video_file.stem[:8]).lower()
    fingerprint = fingerprint_file(video_file)
    now = _utcnow()
    relative_path = video_file.resolve().relative_to(download_dir.resolve()).as_posix()
    return {
        "fingerprint": fingerprint,
        "file_hash": file_hash,
        "filename": relative_path,
        "filepath": str(video_file.resolve()),
        "size_bytes": video_file.stat().st_size,
        "title": str(meta.get("title") or video_file.stem),
        "thumbnail": str(meta.get("thumbnail") or ""),
        "duration": _coerce_float(meta.get("duration")),
        "source_url": str(meta.get("webpage_url") or meta.get("source_url") or ""),
        "meta_json": json.dumps(meta, ensure_ascii=False),
        "created_at": now,
        "last_seen_at": now,
    }


def _read_meta(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("读取 meta.json 失败: %s, error=%s", path, exc)
        return {}
    return data if isinstance(data, dict) else {}

def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()
