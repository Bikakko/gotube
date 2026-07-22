"""
管理页面专用 API 路由

提供登录认证、视频管理、导出、统计等功能。
所有接口都需要 Bearer token 验证。
"""

import json
import logging
import secrets
import shutil
import tempfile
import time
import zipfile
from collections import Counter
from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from starlette.background import BackgroundTask
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from .auth import get_current_user, get_db, require_admin
from .config import settings
from .cookie_store import (
    delete_uploaded_cookies_file,
    diagnose_cookie_content,
    get_active_cookies_file_for_status,
    get_data_dir,
    get_runtime_cookies_source,
    get_uploaded_cookies_path,
    set_runtime_cookies_source,
)
from .db import AuthToken, MediaAsset, User, UserVideoItem
from .health_checks import collect_runtime_health, read_runtime_logs
from .models import (
    ChangePasswordRequest,
    CreateInviteRequest,
    CreateUserRequest,
    InviteResponse,
    LoginRequest,
    UpdateUserRequest,
    UserResponse,
)
from .invites import create_invite, list_invites, revoke_invite
from .user_profile import build_user_identity, display_name_key, validate_display_name, validate_new_password
from .video_library import (
    admin_delete_media_asset,
    list_admin_media_assets,
    list_admin_media_assets_page,
    list_user_video_items,
)

logger = logging.getLogger(__name__)

router = APIRouter()
_BATCH_DELETE_LIMIT = 100


def get_local_timezone() -> ZoneInfo | timezone:
    try:
        return ZoneInfo("Asia/Shanghai")
    except Exception:
        return timezone(timedelta(hours=8))


def _raise_internal_admin_error(user_message: str, exc: Exception) -> None:
    logger.exception("%s: %s", user_message, exc)
    raise HTTPException(status_code=500, detail=user_message) from exc


# ── Token 管理 ──


# Token 有效期：约 100 年，等效于永不过期（仅主动登出失效）。
# 写入真实远未来日期而非 NULL，以兼容历史 NOT NULL 约束的数据库，无需迁移。
_TOKEN_TTL_SECONDS = 100 * 365 * 24 * 3600


def generate_token(db: Session, user_id: int, username: str, role: str) -> str:
    """生成 token 并存入数据库"""
    token = secrets.token_hex(32)
    expiry = datetime.now(UTC) + timedelta(seconds=_TOKEN_TTL_SECONDS)

    auth_token = AuthToken(
        token=token,
        user_id=user_id,
        expires_at=expiry,
        is_active=True,
    )
    db.add(auth_token)
    db.commit()

    logger.info("生成 token: user=%s, role=%s, 过期时间: %s",
                username, role, expiry.isoformat())
    return token


# ── 辅助函数 ──


def _extract_source_from_url(url: str) -> str:
    """从视频 URL 提取来源平台"""
    from urllib.parse import urlparse

    try:
        hostname = urlparse(url).hostname or ""
    except Exception:
        return "Unknown"

    source_map = {
        "youtube.com": "YouTube",
        "youtu.be": "YouTube",
        "bilibili.com": "Bilibili",
        "b23.tv": "Bilibili",
        "twitter.com": "Twitter/X",
        "x.com": "Twitter/X",
        "douyin.com": "抖音",
        "acfun.cn": "AcFun",
        "iqiyi.com": "爱奇艺",
        "youku.com": "优酷",
        "qq.com": "腾讯视频",
        "kuaishou.com": "快手",
    }

    for domain, source in source_map.items():
        if domain in hostname:
            return source

    return hostname or "Unknown"


def _get_queue_manager():
    """运行时获取 queue_manager，避免循环导入"""
    from .main import app
    return app.state.queue_manager


def _validate_filename(filename: str, download_dir: Path) -> Path:
    """
    校验文件名，防止路径遍历攻击。

    不使用字符白名单（因为 yt-dlp 生成的标题包含任意 Unicode 字符），
    而是通过路径规范化 + 前缀检查来确保安全。

    Returns:
        文件的绝对路径。

    Raises:
        HTTPException: 文件名包含非法路径字符或路径穿越。
    """
    # 1. 基础非空检查
    if not filename or not filename.strip():
        raise HTTPException(status_code=400, detail="非法文件名")

    # 2. 拒绝绝对路径和父目录跳转
    if filename.startswith('/') or '..' in filename.split('/'):
        raise HTTPException(status_code=403, detail="非法文件路径")

    # 3. 解析为绝对路径
    filepath = (download_dir / filename).resolve()

    # 4. 确保路径在下载目录内（核心防护）
    try:
        filepath.relative_to(download_dir.resolve())
    except ValueError as e:
        raise HTTPException(status_code=403, detail="非法文件路径") from e

    return filepath


def _read_meta_from_dir(dir_path: Path) -> dict:
    """从目录读取 meta.json 元数据"""
    meta_path = dir_path / "meta.json"
    if not meta_path.exists():
        return {}
    try:
        with open(meta_path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("读取元数据失败 %s: %s", meta_path, e)
        return {}


def _list_all_videos(download_dir: Path) -> list[dict[str, Any]]:
    """
    扫描下载目录，返回所有视频信息列表。
    """
    from .downloader import VIDEO_EXTENSIONS
    
    videos = []

    for video_file in download_dir.rglob("*"):
        if not video_file.is_file():
            continue
        if video_file.suffix.lower() not in VIDEO_EXTENSIONS:
            continue

        # 跳过 guest 临时文件
        try:
            rel = video_file.relative_to(download_dir)
            rel_str = str(rel)
            if rel_str.startswith("temp_guest/") or rel_str.startswith("temp_guest\\"):
                continue
        except ValueError:
            pass

        meta = _read_meta_from_dir(video_file.parent)
        if not meta:
            continue
        
        stat = video_file.stat()
        dir_name = video_file.parent.name
        
        # 从目录名提取 hash（格式：标题_hash）
        file_hash = meta.get("file_hash", "")
        if not file_hash and "_" in dir_name:
            file_hash = dir_name.rsplit("_", 1)[-1]
        
        # 提取来源
        url = meta.get("url", "")
        source = _extract_source_from_url(url)
        
        # 缩略图处理
        thumbnail = meta.get("thumbnail", "")
        if thumbnail and not thumbnail.startswith(("http://", "https://")):
            # 本地缩略图，转换为 API URL
            thumbnail = f"/api/thumbnail/{file_hash}"
        
        videos.append({
            "filename": str(video_file.relative_to(download_dir)),
            "filepath": str(video_file.resolve()),
            "title": meta.get("title", ""),
            "thumbnail": thumbnail,
            "video_id": meta.get("video_id", ""),
            "duration": meta.get("duration", 0),
            "file_hash": file_hash,
            "url": url,
            "source": source,
            "size": stat.st_size,
            "created_at": meta.get("created_at", datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat()),
            "tags": meta.get("tags", []),
        })
    
    # 按创建时间倒序
    videos.sort(key=lambda x: x["created_at"], reverse=True)
    return videos


def _normalize_route_value(value: Any, fallback: Any = None) -> Any:
    """Support direct unit-test calls where FastAPI Query defaults are not resolved."""
    if value.__class__.__module__.startswith("fastapi."):
        return fallback
    return value


def _media_thumbnail_url(asset: MediaAsset) -> str:
    thumbnail = asset.thumbnail or ""
    if thumbnail and not thumbnail.startswith(("http://", "https://")):
        return f"/api/thumbnail/{asset.file_hash}"
    return thumbnail


def _library_item_thumbnail_url(item: dict[str, Any]) -> str:
    # /api/me/videos/{id}/thumbnail 有归属校验，管理员看他人视频库会 403，
    # 故管理端统一改用无用户作用域的 /api/thumbnail/{file_hash}
    thumbnail = item.get("thumbnail") or ""
    if thumbnail and not thumbnail.startswith(("http://", "https://")):
        return f"/api/thumbnail/{item.get('file_hash', '')}"
    return thumbnail


def _library_video_to_admin_dict(row: dict[str, Any], ref_counts: dict[int, int]) -> dict[str, Any]:
    media_asset_id = row.get("media_asset_id")
    source_url = row.get("source_url", "")
    return {
        **row,
        "item_id": row.get("id"),
        "filepath": "",
        "url": source_url,
        "source": _extract_source_from_url(source_url),
        "created_at": row.get("saved_at") or datetime.now(UTC).isoformat(),
        "tags": [],
        "reference_count": ref_counts.get(media_asset_id, 0) if media_asset_id else 0,
        "is_legacy": False,
    }


def _legacy_media_to_admin_dict(asset: MediaAsset, ref_counts: dict[int, int]) -> dict[str, Any]:
    return {
        "id": f"legacy-{asset.id}",
        "item_id": None,
        "owner_user_id": None,
        "owner_username": "未归属",
        "media_asset_id": asset.id,
        "title": asset.title,
        "filename": asset.filename,
        "filepath": asset.filepath,
        "file_hash": asset.file_hash,
        "share_token": "",
        "share_enabled": False,
        "thumbnail": _media_thumbnail_url(asset),
        "video_id": "",
        "duration": asset.duration or 0,
        "size": asset.size_bytes,
        "source_url": asset.source_url,
        "url": asset.source_url,
        "source": _extract_source_from_url(asset.source_url),
        "created_at": asset.created_at.isoformat() if asset.created_at else datetime.now(UTC).isoformat(),
        "tags": [],
        "reference_count": ref_counts.get(asset.id, 0),
        "is_legacy": True,
    }


def _admin_media_asset_to_admin_dict(row: dict[str, Any]) -> dict[str, Any]:
    row = {**row}
    thumbnail = row.get("thumbnail") or ""
    if thumbnail and not thumbnail.startswith(("http://", "https://")):
        row["thumbnail"] = f"/api/thumbnail/{row.get('file_hash', '')}"
    row["source"] = _extract_source_from_url(row.get("source_url") or row.get("url") or "")
    return row


def _list_admin_media_videos(
    db: Session,
    admin: User,
    *,
    owner_user_id: int | None = None,
    owner: str | None = None,
) -> list[dict[str, Any]]:
    videos = [
        _admin_media_asset_to_admin_dict(row)
        for row in list_admin_media_assets(db, admin, owner_user_id=owner_user_id, owner=owner)
    ]
    videos.sort(key=lambda row: row.get("created_at") or "", reverse=True)
    return videos


def _cleanup_temp_file(path: str) -> None:
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        logger.warning("删除临时文件失败: %s", path)


def _update_meta_in_dir(dir_path: Path, updates: dict) -> None:
    """更新目录下的 meta.json 文件"""
    meta_path = dir_path / "meta.json"
    if not meta_path.exists():
        return
    
    try:
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        
        meta.update(updates)
        
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, OSError) as e:
        logger.error("更新元数据失败 %s: %s", meta_path, e)


def _classify_video_time(created_at_str: str) -> str:
    """根据创建时间分类视频（使用本地时区）"""
    try:
        # 使用本地时区（Asia/Shanghai）
        local_tz = ZoneInfo("Asia/Shanghai")
        created_at = datetime.fromisoformat(created_at_str)
        now = datetime.now(local_tz)

        # 转换为本地时区比较
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=local_tz)
        else:
            created_at = created_at.astimezone(local_tz)

        # 从宽到窄判断：先判断大范围，再判断小范围
        # 本自然月（从1号开始）
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if created_at >= month_start:
            # 在本月内，再判断是否在本周
            today_weekday = now.weekday()  # 0=周一, 6=周日
            week_start = now - timedelta(days=today_weekday)
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
            if created_at >= week_start:
                # 在本周内，再判断是否是今天（用日期比较而不是时间差）
                today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                if created_at >= today_start:
                    return "today"
                return "week"
            return "month"
        else:
            return "earlier"
    except Exception:
        return "earlier"


def _filter_videos_by_time_range(videos: list, time_filter: str) -> list:
    """
    按时间范围筛选视频（包含范围，而非互斥分类）。
    
    - today: 今天（从0点开始）
    - week: 本周（从周一0点开始，包含今天）
    - month: 本月（从1号0点开始，包含本周和今天）
    - earlier: 更早（本月1号0点之前的所有视频）
    """
    local_tz = get_local_timezone()
    now = datetime.now(local_tz)

    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    today_weekday = now.weekday()
    week_start = now - timedelta(days=today_weekday)
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    if time_filter == "today":
        threshold = today_start
    elif time_filter == "week":
        threshold = week_start
    elif time_filter == "month":
        threshold = month_start
    elif time_filter == "earlier":
        return [
            v for v in videos
            if (created_at := _try_get_video_local_time(v.get("created_at"))) is not None
            and created_at < month_start
        ]
    else:
        return videos

    return [
        v for v in videos
        if (created_at := _try_get_video_local_time(v.get("created_at"))) is not None
        and created_at >= threshold
    ]


def _try_get_video_local_time(created_at: Any) -> datetime | None:
    try:
        return _get_video_local_time(created_at)
    except (TypeError, ValueError):
        return None


def _get_video_local_time(created_at: datetime | str) -> datetime:
    """
    获取视频创建时间的本地时区表示。
    """
    if isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    local_tz = get_local_timezone()
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    created_at = created_at.astimezone(local_tz)
    return created_at


# ── 认证 API ──


@router.post("/login")
async def admin_login(
    body: LoginRequest,
    db: Session = Depends(get_db),
) -> dict:
    """
    管理页面登录。
    """
    import bcrypt

    user = db.query(User).filter(User.username == body.username).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    # 验证密码
    if not bcrypt.checkpw(body.password.encode('utf-8'), user.password_hash.encode('utf-8')):
        raise HTTPException(status_code=401, detail="用户名或密码错误")


    # 更新最后登录时间
    user.last_login = datetime.now(UTC)
    db.commit()

    token = generate_token(db, user.id, user.username, user.role)
    return {
        "token": token,
        "user": build_user_identity(user),
    }


@router.get("/auth/check")
async def auth_check(current_user: User = Depends(get_current_user)) -> dict:
    """
    检查当前 token 是否有效，返回用户信息。
    """
    return {
        "valid": True,
        "user": build_user_identity(current_user),
    }


@router.post("/auth/logout")
async def auth_logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    登出，使当前 token 失效。
    """
    auth_header = request.headers.get("Authorization", "")
    token = auth_header[7:].strip() if auth_header.startswith("Bearer ") else None
    
    if token:
        auth_token = db.query(AuthToken).filter(
            AuthToken.token == token,
            AuthToken.is_active == True,
        ).first()
        
        if auth_token:
            auth_token.is_active = False
            db.commit()
            logger.info("用户 %s 主动登出", current_user.username)
    
    return {"success": True}


# ── 用户管理 API ──


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list:
    """获取用户列表 (仅限 admin)"""
    users = db.query(User).all()
    video_counts = {
        int(user_id): int(count)
        for user_id, count in (
            db.query(UserVideoItem.owner_user_id, func.count(UserVideoItem.id))
            .filter(UserVideoItem.deleted_at.is_(None))
            .group_by(UserVideoItem.owner_user_id)
            .all()
        )
    }
    result = []
    for u in users:
        data = u.to_dict()
        data["video_count"] = video_counts.get(u.id, 0)
        data["is_system_account"] = False
        # 标记 admin 权限账号为系统账号
        if u.role == "admin":
            data["is_system_account"] = True
        result.append(data)
    return result


@router.get("/users/{user_id}/library")
async def get_user_library(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Return one user's video library without mixing it into the global media view."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    items = list_user_video_items(db, admin, owner_user_id=user_id)
    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name or user.username,
            "role": user.role,
            "is_active": user.is_active,
            "storage_quota_mb": user.storage_quota_mb,
            "storage_used_bytes": user.storage_used_bytes,
        },
        "items": [
            {
                **item,
                "source": _extract_source_from_url(item.get("source_url") or ""),
                "thumbnail_url": _library_item_thumbnail_url(item),
            }
            for item in items
        ],
    }


@router.post("/users", response_model=UserResponse)
async def create_user(
    body: CreateUserRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """创建普通用户账号。"""
    if body.role == "admin":
        raise HTTPException(
            status_code=403,
            detail="管理员账号只能通过 .env 配置管理",
        )
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")

    import bcrypt

    display_name = validate_display_name(body.display_name)
    password = validate_new_password(body.password)
    pwd_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    new_user = User(
        username=body.username,
        display_name=display_name,
        display_name_key=display_name_key(display_name),
        password_hash=pwd_hash,
        role=body.role,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user.to_dict()


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    body: UpdateUserRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """更新用户资料与角色信息。"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    fields_set = body.model_fields_set if hasattr(body, "model_fields_set") else getattr(body, "__fields_set__", set())
    if user.role == "admin":
        forbidden = fields_set - {"display_name"}
        if forbidden:
            raise HTTPException(
                status_code=403,
                detail="管理员账号仅允许修改昵称，其他信息请通过 .env 管理",
            )

    if body.username:
        existing = db.query(User).filter(User.username == body.username).first()
        if existing and existing.id != user_id:
            raise HTTPException(status_code=400, detail="用户名已存在")
        user.username = body.username

    if body.display_name is not None:
        user.display_name = validate_display_name(body.display_name)
        user.display_name_key = display_name_key(user.display_name)

    if body.role:
        if body.role == "admin":
            raise HTTPException(
                status_code=403,
                detail="管理员账号只能通过 .env 配置管理",
            )
        user.role = body.role

    if body.is_active is not None:
        user.is_active = body.is_active

    if "storage_quota_mb" in fields_set:
        user.storage_quota_mb = body.storage_quota_mb

    db.commit()
    db.refresh(user)
    return user.to_dict()


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """删除用户 (仅限 admin)"""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="不能删除当前登录账号")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 保护 admin 权限账号
    if user.role == "admin":
        raise HTTPException(
            status_code=403,
            detail="管理员账号不可删除，请通过 .env 配置文件管理"
        )

    db.delete(user)
    db.commit()
    return {"status": "ok"}


@router.put("/users/{user_id}/password")
async def change_password(
    user_id: int,
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """管理员重置普通用户密码，或普通用户修改自己的密码。"""
    is_admin = current_user.role == "admin"
    is_self = current_user.id == user_id

    if not (is_admin or is_self):
        raise HTTPException(status_code=403, detail="权限不足")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.role == "admin":
        raise HTTPException(
            status_code=403,
            detail="管理员密码仅允许通过 .env 配置修改",
        )

    import bcrypt

    new_password = validate_new_password(body.new_password)
    try:
        if bcrypt.checkpw(new_password.encode("utf-8"), user.password_hash.encode("utf-8")):
            raise HTTPException(status_code=400, detail="新密码不能与旧密码相同")
    except ValueError:
        logger.warning("检测用户旧密码哈希失败，继续覆盖设置新密码: user_id=%s", user.id)

    if not is_admin:
        if not body.old_password or not bcrypt.checkpw(body.old_password.encode("utf-8"), user.password_hash.encode("utf-8")):
            raise HTTPException(status_code=400, detail="当前密码错误")

    user.password_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    db.flush()
    db.query(AuthToken).filter(
        AuthToken.user_id == user_id,
        AuthToken.is_active == True,
    ).update({"is_active": False})
    db.commit()
    return {"status": "ok"}


@router.post("/invites", response_model=InviteResponse)
async def create_invite_code(
    body: CreateInviteRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """管理员创建邀请码；明文 code 只在本次响应返回。"""
    result = create_invite(
        db,
        admin,
        max_uses=body.max_uses,
        expires_hours=body.expires_hours,
    )
    db.commit()
    return result


@router.get("/invites", response_model=list[InviteResponse])
async def get_invite_codes(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[dict]:
    """管理员查看邀请码列表，不返回明文 code。"""
    return list_invites(db)


@router.delete("/invites/{invite_id}", response_model=InviteResponse)
async def delete_invite_code(
    invite_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """管理员作废邀请码。"""
    result = revoke_invite(db, invite_id)
    db.commit()
    return result


# ── 视频管理 API ──


@router.get("/videos")
async def get_videos(
    keyword: str | None = Query(None, description="关键词搜索"),
    source: str | None = Query(None, description="来源平台"),
    time: str | None = Query("all", description="时间范围: all/today/week/month/earlier"),
    page: int = Query(1, ge=1, description="页码"),
    per_page: int = Query(20, ge=1, le=100, description="每页数量"),
    owner_user_id: int | None = Query(None, description="按用户过滤"),
    owner: str | None = Query(None, description="归属过滤: all/legacy"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """
    获取视频列表，支持筛选和分页。
    """
    keyword = _normalize_route_value(keyword)
    source = _normalize_route_value(source)
    time = _normalize_route_value(time, "all")
    page = int(_normalize_route_value(page, 1) or 1)
    per_page = int(_normalize_route_value(per_page, 20) or 20)
    owner_user_id = _normalize_route_value(owner_user_id)
    owner = _normalize_route_value(owner)

    has_media_assets = db.query(MediaAsset.id).first() is not None
    if has_media_assets:
        return list_admin_media_assets_page(
            db,
            admin,
            owner_user_id=owner_user_id,
            owner=owner,
            keyword=keyword,
            source=source,
            time_filter=time,
            page=page,
            per_page=per_page,
        )
    else:
        download_dir = settings.get_download_dir()
        videos = _list_all_videos(download_dir)

    # 筛选
    if keyword:
        keyword_lower = keyword.lower()
        videos = [v for v in videos if keyword_lower in v["title"].lower()]

    if source:
        videos = [v for v in videos if v["source"] == source]

    if time and time != "all":
        videos = _filter_videos_by_time_range(videos, time)

    total = len(videos)
    
    # 分页
    start = (page - 1) * per_page
    end = start + per_page
    page_videos = videos[start:end]

    # 获取所有来源列表
    all_sources = list({v["source"] for v in videos})

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if per_page > 0 else 0,
        "videos": page_videos,
        "all_sources": sorted(all_sources),
    }


@router.delete("/videos/{filename:path}")
async def delete_video(
    filename: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """
    删除单个视频（含物理文件和元数据）。
    """
    download_dir = settings.get_download_dir()
    filepath = _validate_filename(filename, download_dir)
    
    if not filepath.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")

    relative_name = str(filepath.relative_to(download_dir)).replace("\\", "/")
    asset = (
        db.query(MediaAsset)
        .filter((MediaAsset.filename == relative_name) | (MediaAsset.filepath == str(filepath.resolve())))
        .first()
    )
    if asset:
        result = admin_delete_media_asset(db, admin, asset.id, download_dir)
        db.commit()
        try:
            qm = _get_queue_manager()
            qm.downloader.invalidate_file_index_cache()
            qm.downloader.invalidate_hash_index()
        except Exception as e:
            logger.warning("删除视频后刷新缓存失败: %s", e)
        return result
    
    deleted_files = []
    parent_dir = filepath.parent
    
    # 删除视频文件
    try:
        filepath.unlink()
        deleted_files.append(str(filepath.relative_to(download_dir)))
        logger.info("已删除视频文件: %s", filepath)
    except OSError as e:
        logger.error("删除视频文件失败: %s, 错误: %s", filepath, e)
        raise HTTPException(status_code=500, detail="删除文件失败") from e
    
    # 删除元数据
    meta_path = parent_dir / "meta.json"
    if meta_path.exists():
        try:
            meta_path.unlink()
            deleted_files.append(str(meta_path.relative_to(download_dir)))
            logger.info("已删除元数据: %s", meta_path)
        except OSError as e:
            logger.warning("删除元数据失败 %s: %s", meta_path, e)
    
    # 删除缩略图等本地文件
    for f in parent_dir.iterdir():
        if f.is_file():
            try:
                f.unlink()
                deleted_files.append(str(f.relative_to(download_dir)))
            except OSError as e:
                logger.warning("删除文件失败 %s: %s", f, e)
    
    # 删除空目录
    try:
        if parent_dir != download_dir and not any(parent_dir.iterdir()):
            parent_dir.rmdir()
            deleted_files.append(str(parent_dir.relative_to(download_dir)) + "/")
            logger.info("已删除空目录: %s", parent_dir)
    except OSError as e:
        logger.warning("删除空目录失败 %s: %s", parent_dir, e)

    # 刷新缓存，避免 hash 索引中残留已删除文件的引用
    try:
        qm = _get_queue_manager()
        qm.downloader.invalidate_file_index_cache()
        qm.downloader.invalidate_hash_index()
        logger.info("删除视频后已刷新缓存")
    except Exception as e:
        logger.warning("删除视频后刷新缓存失败: %s", e)

    return {"status": "ok", "deleted_files": deleted_files}


@router.delete("/media-assets/{media_asset_id}")
async def delete_media_asset(
    media_asset_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """管理员维护性删除：物理删除媒体并移除所有用户库记录。"""
    result = admin_delete_media_asset(db, admin, media_asset_id, settings.get_download_dir())
    db.commit()
    try:
        qm = _get_queue_manager()
        qm.downloader.invalidate_file_index_cache()
        qm.downloader.invalidate_hash_index()
    except Exception as e:
        logger.warning("维护性删除后刷新缓存失败: %s", e)
    return result


@router.post("/videos/batch-delete")
async def batch_delete_videos(
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """
    批量删除视频。
    
    请求体: {"media_asset_ids": [1, 2]} 或 {"filenames": ["file1.mp4", "file2.mp4"]}
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="请求体格式错误")

    media_asset_ids = body.get("media_asset_ids", [])
    filenames = body.get("filenames", [])
    if media_asset_ids and not isinstance(media_asset_ids, list):
        raise HTTPException(status_code=400, detail="media_asset_ids 必须是数组")
    if filenames and not isinstance(filenames, list):
        raise HTTPException(status_code=400, detail="filenames 必须是数组")
    if not media_asset_ids and not filenames:
        raise HTTPException(status_code=400, detail="缺少 media_asset_ids 或 filenames 参数")
    if len(media_asset_ids) > _BATCH_DELETE_LIMIT or len(filenames) > _BATCH_DELETE_LIMIT:
        raise HTTPException(status_code=400, detail=f"批量删除最多允许 {_BATCH_DELETE_LIMIT} 项")

    results = []

    if media_asset_ids:
        for raw_media_asset_id in media_asset_ids:
            try:
                media_asset_id = int(raw_media_asset_id)
                result = admin_delete_media_asset(db, admin, media_asset_id, settings.get_download_dir())
                results.append({
                    "media_asset_id": media_asset_id,
                    "filename": result.get("filename", ""),
                    "status": "deleted",
                })
                logger.info("批量维护删除媒体资产: %s", media_asset_id)
            except ValueError:
                results.append({"media_asset_id": raw_media_asset_id, "status": "error", "reason": "非法媒体 ID"})
            except HTTPException as e:
                results.append({
                    "media_asset_id": raw_media_asset_id,
                    "status": "error",
                    "reason": e.detail if isinstance(e.detail, str) else "删除失败",
                })
            except Exception:
                logger.exception("批量维护删除媒体资产失败: id=%s", raw_media_asset_id)
                results.append({"media_asset_id": raw_media_asset_id, "status": "error", "reason": "删除失败"})
    else:
        download_dir = settings.get_download_dir()
        for filename in filenames:
            try:
                filepath = _validate_filename(filename, download_dir)
                if not filepath.is_file():
                    results.append({"filename": filename, "status": "not_found"})
                    continue

                parent_dir = filepath.parent

                filepath.unlink()

                for f in parent_dir.iterdir():
                    if f.is_file():
                        try:
                            f.unlink()
                        except OSError:
                            pass

                if parent_dir != download_dir and not any(parent_dir.iterdir()):
                    try:
                        parent_dir.rmdir()
                    except OSError:
                        pass

                results.append({"filename": filename, "status": "deleted"})
                logger.info("批量删除旧视频文件: %s", filename)

            except HTTPException:
                results.append({"filename": filename, "status": "error", "reason": "非法文件名"})
            except Exception as e:
                results.append({"filename": filename, "status": "error", "reason": str(e)})

    success = sum(1 for r in results if r["status"] == "deleted")
    if success > 0 and media_asset_ids:
        db.commit()

    # 如果有文件被删除，刷新缓存
    if success > 0:
        try:
            qm = _get_queue_manager()
            qm.downloader.invalidate_file_index_cache()
            qm.downloader.invalidate_hash_index()
            logger.info("批量删除后已刷新缓存")
        except Exception as e:
            logger.warning("批量删除后刷新缓存失败: %s", e)

    return {
        "status": "ok",
        "total": len(media_asset_ids) or len(filenames),
        "success": success,
        "failed": (len(media_asset_ids) or len(filenames)) - success,
        "results": results,
    }


@router.put("/videos/{filename:path}/tags")
async def update_video_tags(
    filename: str,
    request: Request,
    admin: User = Depends(require_admin),
) -> dict:
    """
    更新视频标签。
    
    请求体: {"tags": ["tag1", "tag2"]}
    """
    download_dir = settings.get_download_dir()
    filepath = _validate_filename(filename, download_dir)
    
    if not filepath.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="请求体格式错误")
    
    tags = body.get("tags", [])
    if not isinstance(tags, list):
        raise HTTPException(status_code=400, detail="tags 必须是数组")
    
    # 去重并过滤空字符串
    tags = list({t.strip() for t in tags if t.strip()})
    
    # 更新元数据
    dir_path = filepath.parent
    _update_meta_in_dir(dir_path, {"tags": tags})
    
    return {"status": "ok", "tags": tags}


# ── 导出 API ──


@router.post("/export/zip")
async def export_zip(
    request: Request,
    admin: User = Depends(require_admin),
) -> StreamingResponse:
    """
    导出选中视频为 ZIP 文件。
    
    请求体: {"filenames": ["file1.mp4", ...]} 或 {"all": true}
    """
    download_dir = settings.get_download_dir()
    
    try:
        body = await request.json()
    except Exception:
        body = {}
    
    # 获取要导出的文件列表
    if body.get("all"):
        all_videos = _list_all_videos(download_dir)
        filenames = [v["filename"] for v in all_videos]
    else:
        filenames = body.get("filenames", [])
        if not filenames:
            raise HTTPException(status_code=400, detail="缺少 filenames 参数")
    
    # 创建 ZIP 文件（流式）
    temp_zip = tempfile.NamedTemporaryFile(prefix="gotube-export-", suffix=".zip", delete=False)
    temp_zip_path = Path(temp_zip.name)
    temp_zip.close()

    with zipfile.ZipFile(temp_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename in filenames:
            try:
                filepath = _validate_filename(filename, download_dir)
                if not filepath.is_file():
                    logger.warning("导出 ZIP 时文件不存在: %s", filename)
                    continue

                zf.write(filepath, filename)

                meta_path = filepath.parent / "meta.json"
                if meta_path.exists():
                    meta_name = f"{filepath.parent.name}/meta.json"
                    zf.write(meta_path, meta_name)

                for f in filepath.parent.iterdir():
                    if f.is_file() and f.name.startswith("thumbnail"):
                        thumb_name = f"{filepath.parent.name}/{f.name}"
                        zf.write(f, thumb_name)
            except Exception as e:
                logger.error("添加文件到 ZIP 失败 %s: %s", filename, e)

    return FileResponse(
        temp_zip_path,
        media_type="application/zip",
        filename="gotube_export.zip",
        background=BackgroundTask(_cleanup_temp_file, str(temp_zip_path)),
    )


@router.post("/export/json")
async def export_json(
    request: Request,
    admin: User = Depends(require_admin),
) -> Response:
    """
    导出所有视频元数据为 JSON 文件。
    """
    download_dir = settings.get_download_dir()
    videos = _list_all_videos(download_dir)
    
    # 移除内部字段，只保留元数据
    export_data = []
    for v in videos:
        export_data.append({
            "title": v["title"],
            "thumbnail": v["thumbnail"],
            "video_id": v["video_id"],
            "duration": v["duration"],
            "file_hash": v["file_hash"],
            "url": v["url"],
            "source": v["source"],
            "size": v["size"],
            "created_at": v["created_at"],
            "tags": v["tags"],
            "filename": v["filename"],
        })
    
    json_bytes = json.dumps(export_data, ensure_ascii=False, indent=2).encode("utf-8")
    
    return Response(
        content=json_bytes,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=\"gotube_metadata.json\""},
    )


@router.post("/export/m3u8")
async def export_m3u8(
    request: Request,
    admin: User = Depends(require_admin),
) -> Response:
    """
    导出选中视频为 m3u8 播放列表。
    
    请求体: {"filenames": ["file1.mp4", ...]} 或 {"all": true}
    """
    download_dir = settings.get_download_dir()
    
    try:
        body = await request.json()
    except Exception:
        body = {}
    
    # 获取要导出的视频列表
    all_videos = _list_all_videos(download_dir)
    
    if body.get("all"):
        videos = all_videos
    else:
        filenames = body.get("filenames", [])
        if not filenames:
            raise HTTPException(status_code=400, detail="缺少 filenames 参数")
        videos = [v for v in all_videos if v["filename"] in filenames]
    
    # 生成 m3u8 内容
    lines = ["#EXTM3U"]
    
    for v in videos:
        duration = int(v.get("duration", 0))
        title = v.get("title", "Unknown").replace(",", "").replace("\n", " ")
        file_hash = v.get("file_hash", "")
        
        # 使用 /watch?v={hash} 作为播放地址
        watch_url = f"/watch?v={file_hash}"
        
        lines.append(f"#EXTINF:{duration},{title}")
        lines.append(watch_url)
    
    content = "\n".join(lines) + "\n"
    
    return Response(
        content=content,
        media_type="audio/x-mpegurl",
        headers={"Content-Disposition": "attachment; filename=\"gotube_playlist.m3u8\""},
    )


# ── 统计 API ──


@router.get("/stats")
async def get_stats(
    admin: User = Depends(require_admin),
) -> dict:
    """
    获取视频统计信息。
    """
    download_dir = settings.get_download_dir()
    videos = _list_all_videos(download_dir)
    
    total = len(videos)
    total_size = sum(v["size"] for v in videos)
    
    # 按来源统计
    source_counter = Counter(v["source"] for v in videos)
    sources = [
        {"name": name, "count": count, "percentage": round(count / total * 100, 1) if total > 0 else 0}
        for name, count in source_counter.most_common()
    ]
    
    # 按时间统计
    time_counter = Counter(_classify_video_time(v["created_at"]) for v in videos)
    times = {
        "today": time_counter.get("today", 0),
        "week": time_counter.get("week", 0),
        "month": time_counter.get("month", 0),
        "earlier": time_counter.get("earlier", 0),
    }
    
    return {
        "total": total,
        "total_size": total_size,
        "sources": sources,
        "times": times,
    }


# ── Cookie 管理 API ──


def _get_or_create_data_dir() -> Path:
    """获取或创建 data 目录（用于存储 cookies 等运行时数据）"""
    return get_data_dir()


def _get_cookies_storage_path() -> Path:
    """获取 cookies 存储路径（固定在 data 目录）"""
    return get_uploaded_cookies_path()


def _parse_cookies_domains(cookies_path: Path) -> list[str]:
    """
    解析 Netscape cookies 文件，提取所有域名。

    Returns:
        去重后的域名列表。
    """
    domains = set()
    try:
        with open(cookies_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # 跳过注释和空行
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 1:
                    domains.add(parts[0])
    except Exception as e:
        logger.warning("解析 cookies 域名失败: %s", e)
    return sorted(domains)


def _parse_domains_from_content(content: str) -> list[str]:
    """
    从 cookies 内容字符串中解析域名。

    Args:
        content: cookies 文本内容。

    Returns:
        去重后的域名列表。
    """
    domains = set()
    for line in content.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 1:
            domains.add(parts[0])
    return sorted(domains)


def _parse_cookie_entries_from_content(content: str) -> tuple[list[str], list[dict[str, str]]]:
    """
    解析 Netscape cookies 内容，提取头部注释和 cookie 记录。

    Cookie 的唯一键使用 (domain, path, name)，避免“按域整体替换”误删同域下其他记录。
    """
    header_lines: list[str] = []
    entries: list[dict[str, str]] = []

    for raw_line in content.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            header_lines.append(stripped)
            continue

        parts = stripped.split("\t")
        if len(parts) < 7:
            continue

        domain = parts[0].strip()
        path = parts[2].strip()
        name = parts[5].strip()
        if not domain or not name:
            continue

        entries.append({
            "domain": domain,
            "path": path,
            "name": name,
            "line": stripped,
        })

    return header_lines, entries


def _cookie_entry_key(entry: dict[str, str]) -> tuple[str, str, str]:
    return (entry["domain"], entry["path"], entry["name"])


def _format_cookie_entry(entry: dict[str, str]) -> str:
    path = entry.get("path") or "/"
    return f'{entry["domain"]} | {entry["name"]} | {path}'


def _analyze_cookie_merge(existing_content: str | None, new_content: str) -> dict[str, Any]:
    """
    生成 cookies 合并预览。

    返回域名级和 cookie 记录级的影响范围，供确认弹窗与接口日志使用。
    """
    _, new_entries = _parse_cookie_entries_from_content(new_content)
    _, existing_entries = _parse_cookie_entries_from_content(existing_content or "")

    new_domains = sorted({entry["domain"] for entry in new_entries})
    existing_domains = sorted({entry["domain"] for entry in existing_entries})

    new_domain_set = set(new_domains)
    existing_domain_set = set(existing_domains)

    existing_by_key = {_cookie_entry_key(entry): entry for entry in existing_entries}
    new_by_key = {_cookie_entry_key(entry): entry for entry in new_entries}

    replace_keys = sorted(set(existing_by_key) & set(new_by_key))
    add_keys = sorted(set(new_by_key) - set(existing_by_key))
    preserved_keys = sorted(set(existing_by_key) - set(new_by_key))

    def _sample(keys: list[tuple[str, str, str]], source: dict[tuple[str, str, str], dict[str, str]]) -> list[str]:
        return [_format_cookie_entry(source[key]) for key in keys[:10]]

    return {
        "new_domains": new_domains,
        "existing_domains": existing_domains,
        "will_replace": sorted(new_domain_set & existing_domain_set),
        "will_add": sorted(new_domain_set - existing_domain_set),
        "replace_count": len(new_domain_set & existing_domain_set),
        "add_count": len(new_domain_set - existing_domain_set),
        "will_affect_other_domains": len(existing_domain_set - new_domain_set) > 0,
        "unchanged_domains": sorted(existing_domain_set - new_domain_set),
        "will_replace_cookie_count": len(replace_keys),
        "will_add_cookie_count": len(add_keys),
        "will_preserve_cookie_count": len(preserved_keys),
        "replace_cookie_samples": _sample(replace_keys, new_by_key),
        "add_cookie_samples": _sample(add_keys, new_by_key),
        "preserve_cookie_samples": _sample(preserved_keys, existing_by_key),
    }


def _merge_cookies_content(existing_content: str, new_content: str) -> str:
    """
    智能合并两个 cookies 内容。

    逻辑：
    1. 解析现有内容和新内容的 cookie 记录
    2. 以 (domain, path, name) 作为唯一键
    3. 新内容仅覆盖同键记录
    4. 其他旧记录保持不变
    5. 新键追加到结果中

    Args:
        existing_content: 现有的 cookies 内容。
        new_content: 新的 cookies 内容。

    Returns:
        合并后的内容。
    """
    existing_header_lines, existing_entries = _parse_cookie_entries_from_content(existing_content)
    new_header_lines, new_entries = _parse_cookie_entries_from_content(new_content)

    merged_entries: dict[tuple[str, str, str], dict[str, str]] = {
        _cookie_entry_key(entry): entry for entry in existing_entries
    }
    for entry in new_entries:
        merged_entries[_cookie_entry_key(entry)] = entry

    result_lines = existing_header_lines or new_header_lines or ["# Netscape HTTP Cookie File"]
    for entry in merged_entries.values():
        result_lines.append(entry["line"])

    return "\n".join(result_lines) + "\n"


def _get_active_cookies_content() -> str | None:
    """
    获取当前活动的 cookies 文件内容。

    Returns:
        文件内容，如果不存在返回 None。
    """
    active_cookies = get_active_cookies_file_for_status()

    if not active_cookies or not active_cookies.exists():
        return None

    try:
        with open(active_cookies, encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.warning("读取 cookies 内容失败: %s", e)
        return None


def _backup_cookies_file(cookies_path: Path) -> Path | None:
    """
    备份现有 cookies 文件。

    Returns:
        备份文件路径，如果不存在返回 None。
    """
    if not cookies_path.exists():
        return None

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    backup_path = cookies_path.parent / f"cookies.txt.bak.{timestamp}"
    try:
        shutil.copy2(cookies_path, backup_path)
        logger.info("已备份 cookies 文件: %s", backup_path.name)
        return backup_path
    except Exception as e:
        logger.error("备份 cookies 失败: %s", e)
        return None


def _validate_cookies_format(content: str) -> tuple[bool, str]:
    """
    验证 cookies 内容格式（Netscape 格式）。

    Netscape 格式要求：
    - 第一行必须是 `# Netscape HTTP Cookie File`
    - 每行 7 个字段，制表符分隔
    - 字段：domain, include_subdomains, path, https_only, expires_at, name, value

    Returns:
        (是否有效, 错误信息)
    """
    lines = content.strip().split("\n")
    
    # 检查第一行注释头
    first_line = lines[0].strip() if lines else ""
    if first_line != "# Netscape HTTP Cookie File":
        return False, "第一行必须是 '# Netscape HTTP Cookie File' 注释头"

    valid_lines = 0

    for i, line in enumerate(lines, 1):
        line = line.strip()
        # 跳过注释和空行
        if not line or line.startswith("#"):
            continue

        parts = line.split("\t")
        if len(parts) < 7:
            return False, f"第 {i} 行格式错误：Netscape 格式应包含 7 个制表符分隔字段（当前 {len(parts)} 个）"

        valid_lines += 1

    if valid_lines == 0:
        return False, "未找到有效的 cookies 数据"

    return True, ""


def _reload_cookies_in_downloader(cookies_path: Path | None) -> None:
    """
    热重载下载器的 cookies 配置。

    调用 Downloader.reload_cookies() 方法。
    """
    try:
        qm = _get_queue_manager()
        qm.downloader.reload_cookies(cookies_path if cookies_path and cookies_path.exists() else None)
    except Exception as e:
        _raise_internal_admin_error("热重载 cookies 失败", e)


@router.get("/cookies/status")
async def get_cookies_status(
    admin: User = Depends(require_admin),
) -> dict:
    """
    获取当前 cookies 状态信息。

    返回：
    - has_cookies: 是否存在 cookies 文件
    - file_size: 文件大小（字节）
    - modified_time: 最后修改时间
    - domains: 包含的域名列表
    - source: 来源（.env 配置或上传）
    """
    try:
        active_cookies = get_active_cookies_file_for_status()

        if not active_cookies or not active_cookies.exists():
            return {
                "has_cookies": False,
                "source": "none",
                "message": "未配置运行时 cookies 文件",
                "diagnostics": diagnose_cookie_content(""),
            }

        # 获取文件信息
        stat = active_cookies.stat()
        file_size = stat.st_size
        modified_time = datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat()

        # 解析域名
        domains = _parse_cookies_domains(active_cookies)
        content = active_cookies.read_text(encoding="utf-8")

        return {
            "has_cookies": True,
            "file_size": file_size,
            "file_size_human": f"{file_size / 1024:.1f} KB",
            "modified_time": modified_time,
            "domains": domains,
            "domain_count": len(domains),
            "source": get_runtime_cookies_source(),
            "file_path": str(active_cookies.relative_to(settings.project_root)),
            "diagnostics": diagnose_cookie_content(content),
        }
    except Exception as e:
        _raise_internal_admin_error("获取 cookies 状态失败", e)


@router.get("/runtime/health")
async def get_runtime_health(
    admin: User = Depends(require_admin),
) -> dict:
    """Return release-readiness runtime checks for administrators."""
    return collect_runtime_health()


@router.get("/runtime/logs")
async def get_runtime_logs(
    log_type: str = Query(default="app", pattern="^(app|access)$"),
    line_limit: int = Query(default=120, ge=1, le=300),
    admin: User = Depends(require_admin),
) -> dict:
    """Return recent runtime log lines for administrators."""
    return read_runtime_logs(log_type=log_type, line_limit=line_limit)


@router.post("/cookies/check_merge")
async def check_cookies_merge(
    request: Request,
    admin: User = Depends(require_admin),
) -> dict:
    """
    预检查上传的 cookies 内容，返回将影响的域名。

    用于前端显示确认对话框，不实际保存文件。
    """
    try:
        content_type = request.headers.get("Content-Type", "")
        content = ""

        # 解析内容（与 upload_cookies 相同逻辑）
        if "multipart/form-data" in content_type:
            form = await request.form()
            file = form.get("file")
            if not file:
                raise HTTPException(status_code=400, detail="缺少 file 字段")
            if hasattr(file, "file") and hasattr(file.file, "read"):
                content = (await file.read()).decode("utf-8")
            elif hasattr(file, "read"):
                content = file.read().decode("utf-8")
            else:
                content = str(file)
        elif "application/json" in content_type:
            body = await request.json()
            content = body.get("content", "").strip()
        else:
            raise HTTPException(status_code=400, detail="不支持的 Content-Type")

        if not content:
            raise HTTPException(status_code=400, detail="cookies 内容为空")

        # 验证格式
        is_valid, error_msg = _validate_cookies_format(content)
        if not is_valid:
            raise HTTPException(status_code=400, detail=f"cookies 格式无效: {error_msg}")

        existing_content = _get_active_cookies_content()
        summary = _analyze_cookie_merge(existing_content, content)

        return {"status": "ok", **summary}
    except HTTPException:
        raise
    except Exception as e:
        _raise_internal_admin_error("预检查失败", e)


@router.post("/cookies/upload")
async def upload_cookies(
    request: Request,
    mode: str = Query(default="replace", description="上传模式：replace（替换整个文件）或 merge（智能合并）"),
    admin: User = Depends(require_admin),
) -> dict:
    """
    上传/更新 cookies 文件。

    支持两种方式：
    1. multipart/form-data 文件上传（file 字段）
    2. JSON 请求体（content 字段，文本内容）

    模式：
    - replace: 完全替换现有 cookies 文件（默认）
    - merge: 智能合并，按域名替换，不影响其他平台

    自动备份旧文件，热重载下载器配置。
    """
    cookies_path = _get_cookies_storage_path()
    content = ""

    try:
        # 判断请求类型
        content_type = request.headers.get("Content-Type", "")

        if "multipart/form-data" in content_type:
            # 文件上传方式
            form = await request.form()
            file = form.get("file")
            if not file:
                raise HTTPException(status_code=400, detail="缺少 file 字段")

            # 检查文件类型
            if hasattr(file, "filename") and file.filename:
                if not file.filename.endswith(".txt"):
                    raise HTTPException(status_code=400, detail="仅支持 .txt 格式文件")

            # 读取内容
            if hasattr(file, "file") and hasattr(file.file, "read"):
                # FastAPI UploadFile 对象
                content = (await file.read()).decode("utf-8")
            elif hasattr(file, "read"):
                # 其他文件对象
                content = file.read().decode("utf-8")
            else:
                content = str(file)

        elif "application/json" in content_type:
            # JSON 文本方式
            try:
                body = await request.json()
                content = body.get("content", "").strip()
            except Exception:
                raise HTTPException(status_code=400, detail="请求体格式错误")
        else:
            raise HTTPException(status_code=400, detail="不支持的 Content-Type")

        if not content:
            raise HTTPException(status_code=400, detail="cookies 内容为空")

        # 验证格式
        is_valid, error_msg = _validate_cookies_format(content)
        if not is_valid:
            raise HTTPException(status_code=400, detail=f"cookies 格式无效: {error_msg}")

        # 检查大小限制（1MB）
        if len(content.encode("utf-8")) > 1024 * 1024:
            raise HTTPException(status_code=400, detail="cookies 文件过大（最大 1MB）")

        # 根据模式处理内容
        final_content = content
        mode_message = "完全替换模式"

        if mode == "merge":
            # 智能合并模式
            existing_content = _get_active_cookies_content()
            if existing_content:
                summary = _analyze_cookie_merge(existing_content, content)
                final_content = _merge_cookies_content(existing_content, content)
                mode_message = (
                    "智能合并模式"
                    f"（覆盖 {summary['will_replace_cookie_count']} 条 Cookie，"
                    f"新增 {summary['will_add_cookie_count']} 条，"
                    f"保留 {summary['will_preserve_cookie_count']} 条）"
                )
            else:
                # 没有现有文件，直接保存
                mode_message = "智能合并模式（新文件）"

        # 备份旧文件
        backup_path = _backup_cookies_file(cookies_path)

        # 保存 cookies
        try:
            with open(cookies_path, "w", encoding="utf-8") as f:
                f.write(final_content)
            set_runtime_cookies_source("upload")
            logger.info("cookies 文件已更新: %s (%d bytes, %s)", cookies_path, len(final_content), mode_message)
        except Exception as e:
            _raise_internal_admin_error("保存 cookies 失败", e)

        # 热重载下载器
        _reload_cookies_in_downloader(cookies_path)

        # 解析最终域名
        domains = _parse_domains_from_content(final_content)

        return {
            "status": "ok",
            "message": f"cookies {mode_message}成功",
            "mode": mode,
            "file_size": len(final_content.encode("utf-8")),
            "file_size_human": f"{len(final_content.encode('utf-8')) / 1024:.1f} KB",
            "domains": domains,
            "domain_count": len(domains),
            "backup": backup_path.name if backup_path else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        _raise_internal_admin_error("上传 cookies 失败", e)


@router.delete("/cookies")
async def delete_cookies(
    admin: User = Depends(require_admin),
) -> dict:
    """
    删除上传的 cookies 文件，恢复到 .env 配置的路径。

    会自动备份后删除。
    """
    cookies_path = _get_cookies_storage_path()

    if not cookies_path.exists():
        raise HTTPException(status_code=404, detail="未找到上传的 cookies 文件")

    try:
        # 备份
        backup_path = _backup_cookies_file(cookies_path)

        # 删除
        delete_uploaded_cookies_file()
        logger.info("已删除上传的 cookies 文件")

        _reload_cookies_in_downloader(None)

        return {
            "status": "ok",
            "message": "cookies 已删除，下载器已停止使用 Cookie",
            "backup": backup_path.name if backup_path else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        _raise_internal_admin_error("删除 cookies 失败", e)

