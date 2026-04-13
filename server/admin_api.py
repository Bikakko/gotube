"""
管理页面专用 API 路由

提供登录认证、视频管理、导出、统计等功能。
所有接口都需要 Bearer token 验证。
"""

import json
import logging
import secrets
import shutil
import time
import zipfile
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy.orm import Session

from .config import settings
from .db import User, get_session
from .models import (
    ChangePasswordRequest,
    CreateUserRequest,
    LoginRequest,
    UpdateUserRequest,
    UserResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Token 管理 ──


# 内存存储 token: {token: {user_id, username, role, expiry}}
_admin_tokens: dict[str, dict] = {}

# Token 有效期：120 小时
_TOKEN_TTL_SECONDS = 120 * 3600


def generate_token(user_id: int, username: str, role: str) -> str:
    """生成包含用户信息的 token 并存入内存"""
    token = secrets.token_hex(32)
    expiry = time.time() + _TOKEN_TTL_SECONDS
    _admin_tokens[token] = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "expiry": expiry,
    }
    logger.info("生成 token: user=%s, role=%s, 过期时间: %s", 
                username, role, datetime.fromtimestamp(expiry, tz=UTC).isoformat())
    return token


def verify_token(token: str | None) -> dict | None:
    """验证 token 并返回 payload"""
    if not token or token not in _admin_tokens:
        return None
    
    data = _admin_tokens[token]
    if time.time() > data["expiry"]:
        _admin_tokens.pop(token, None)
        return None
    
    # 数据库检查用户状态
    try:
        with get_session() as db:
            user = db.query(User).filter(User.id == data["user_id"]).first()
            if not user or not user.is_active:
                _admin_tokens.pop(token, None)
                return None
            # 角色如果变了，同步更新 token 里的角色（可选）
            if user.role != data["role"]:
                data["role"] = user.role
    except Exception as e:
        logger.error("Token 查库校验失败: %s", e)
        return None

    # 续期
    data["expiry"] = time.time() + _TOKEN_TTL_SECONDS
    return data


def cleanup_expired_tokens() -> None:
    """清理过期 token"""
    now = time.time()
    expired = [t for t, data in _admin_tokens.items() if now > data["expiry"]]
    for t in expired:
        _admin_tokens.pop(t, None)


async def verify_admin_authorization(request: Request) -> dict:
    """
    依赖注入：验证 Authorization Header 中的 Bearer token。
    
    Returns:
        token payload 字典。
    """
    cleanup_expired_tokens()
    
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未授权访问")
    
    token = auth_header[7:].strip()
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")
    
    return payload


async def get_db():
    """依赖注入：获取数据库会话"""
    with get_session() as session:
        yield session


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
    """根据创建时间分类视频"""
    try:
        created_at = datetime.fromisoformat(created_at_str)
        now = datetime.now(UTC)
        
        # 转换为同一时区比较
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        
        delta = now - created_at
        
        if delta.days == 0:
            return "today"
        elif delta.days <= 7:
            return "week"
        elif delta.days <= 30:
            return "month"
        else:
            return "earlier"
    except Exception:
        return "earlier"


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
    
    token = generate_token(user.id, user.username, user.role)
    return {
        "token": token,
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
        }
    }


@router.get("/auth/check")
async def auth_check(payload: dict = Depends(verify_admin_authorization)) -> dict:
    """
    检查当前 token 是否有效，返回用户信息。
    """
    return {
        "valid": True,
        "user": {
            "id": payload["user_id"],
            "username": payload["username"],
            "role": payload["role"],
        }
    }


# ── 用户管理 API ──


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    payload: dict = Depends(verify_admin_authorization),
    db: Session = Depends(get_db),
) -> list:
    """获取用户列表 (仅限 admin)"""
    if payload["role"] != "admin":
        raise HTTPException(status_code=403, detail="权限不足")
    
    users = db.query(User).all()
    return [u.to_dict() for u in users]


@router.post("/users", response_model=UserResponse)
async def create_user(
    body: CreateUserRequest,
    payload: dict = Depends(verify_admin_authorization),
    db: Session = Depends(get_db),
) -> dict:
    """创建新用户 (仅限 admin)"""
    if payload["role"] != "admin":
        raise HTTPException(status_code=403, detail="权限不足")
    
    # 检查用户名冲突
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    from passlib.hash import bcrypt
    
    new_user = User(
        username=body.username,
        password_hash=bcrypt.hash(body.password),
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
    payload: dict = Depends(verify_admin_authorization),
    db: Session = Depends(get_db),
) -> dict:
    """更新用户信息 (仅限 admin)"""
    if payload["role"] != "admin":
        raise HTTPException(status_code=403, detail="权限不足")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    if body.username:
        # 检查冲突
        existing = db.query(User).filter(User.username == body.username).first()
        if existing and existing.id != user_id:
            raise HTTPException(status_code=400, detail="用户名已存在")
        user.username = body.username
    
    if body.role:
        user.role = body.role
    
    if body.is_active is not None:
        user.is_active = body.is_active
    
    db.commit()
    return user.to_dict()


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    payload: dict = Depends(verify_admin_authorization),
    db: Session = Depends(get_db),
) -> dict:
    """删除用户 (仅限 admin)"""
    if payload["role"] != "admin":
        raise HTTPException(status_code=403, detail="权限不足")
    
    if user_id == payload["user_id"]:
        raise HTTPException(status_code=400, detail="不能删除当前登录账号")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    db.delete(user)
    db.commit()
    return {"status": "ok"}


@router.put("/users/{user_id}/password")
async def change_password(
    user_id: int,
    body: ChangePasswordRequest,
    payload: dict = Depends(verify_admin_authorization),
    db: Session = Depends(get_db),
) -> dict:
    """修改密码 (本人或 admin)"""
    is_admin = payload["role"] == "admin"
    is_self = payload["user_id"] == user_id
    
    if not (is_admin or is_self):
        raise HTTPException(status_code=403, detail="权限不足")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    import bcrypt
    
    # 如果不是 admin，必须验证旧密码
    if not is_admin:
        if not body.old_password or not bcrypt.checkpw(body.old_password.encode('utf-8'), user.password_hash.encode('utf-8')):
            raise HTTPException(status_code=400, detail="旧密码错误")
    
    salt = bcrypt.gensalt()
    user.password_hash = bcrypt.hashpw(body.new_password.encode('utf-8'), salt).decode('utf-8')
    db.commit()
    
    # 修改密码后使所有 token 失效
    keys_to_del = [t for t, data in _admin_tokens.items() if data["user_id"] == user_id]
    for k in keys_to_del:
        _admin_tokens.pop(k, None)
        
    return {"status": "ok"}


# ── 视频管理 API ──


@router.get("/videos")
async def get_videos(
    keyword: str | None = Query(None, description="关键词搜索"),
    source: str | None = Query(None, description="来源平台"),
    time: str | None = Query("all", description="时间范围: all/today/week/month/earlier"),
    tags: str | None = Query(None, description="标签过滤，逗号分隔"),
    page: int = Query(1, ge=1, description="页码"),
    per_page: int = Query(20, ge=1, le=100, description="每页数量"),
    payload: dict = Depends(verify_admin_authorization),
) -> dict:
    """
    获取视频列表，支持筛选和分页。
    """
    download_dir = settings.get_download_dir()
    videos = _list_all_videos(download_dir)
    
    # 筛选
    if keyword:
        keyword_lower = keyword.lower()
        videos = [v for v in videos if keyword_lower in v["title"].lower()]
    
    if source:
        videos = [v for v in videos if v["source"] == source]
    
    if time and time != "all":
        videos = [v for v in videos if _classify_video_time(v["created_at"]) == time]
    
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        if tag_list:
            videos = [v for v in videos if any(t in v.get("tags", []) for t in tag_list)]
    
    total = len(videos)
    
    # 分页
    start = (page - 1) * per_page
    end = start + per_page
    page_videos = videos[start:end]
    
    # 获取所有可用的标签列表（用于前端标签筛选下拉）
    all_tags = set()
    for v in videos:
        all_tags.update(v.get("tags", []))
    
    # 获取所有来源列表
    all_sources = list({v["source"] for v in videos})
    
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if per_page > 0 else 0,
        "videos": page_videos,
        "all_tags": sorted(all_tags),
        "all_sources": sorted(all_sources),
    }


@router.delete("/videos/{filename:path}")
async def delete_video(
    filename: str,
    payload: dict = Depends(verify_admin_authorization),
) -> dict:
    """
    删除单个视频（含物理文件和元数据）。
    """
    if payload["role"] == "readonly":
        raise HTTPException(status_code=403, detail="权限不足")

    download_dir = settings.get_download_dir()
    filepath = _validate_filename(filename, download_dir)
    
    if not filepath.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    
    deleted_files = []
    parent_dir = filepath.parent
    
    # 删除视频文件
    try:
        filepath.unlink()
        deleted_files.append(str(filepath.relative_to(download_dir)))
        logger.info("已删除视频文件: %s", filepath)
    except OSError as e:
        logger.error("删除视频文件失败: %s, 错误: %s", filepath, e)
        raise HTTPException(status_code=500, detail=f"删除文件失败: {e}") from e
    
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
    
    return {"status": "ok", "deleted_files": deleted_files}


@router.post("/videos/batch-delete")
async def batch_delete_videos(
    request: Request,
    payload: dict = Depends(verify_admin_authorization),
) -> dict:
    """
    批量删除视频。
    
    请求体: {"filenames": ["file1.mp4", "file2.mp4"]}
    """
    if payload["role"] == "readonly":
        raise HTTPException(status_code=403, detail="权限不足")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="请求体格式错误")
    
    filenames = body.get("filenames", [])
    if not filenames or not isinstance(filenames, list):
        raise HTTPException(status_code=400, detail="缺少 filenames 参数")
    
    download_dir = settings.get_download_dir()
    results = []
    
    for filename in filenames:
        try:
            filepath = _validate_filename(filename, download_dir)
            if not filepath.is_file():
                results.append({"filename": filename, "status": "not_found"})
                continue
            
            parent_dir = filepath.parent
            
            # 删除视频文件
            filepath.unlink()
            
            # 删除元数据和缩略图
            for f in parent_dir.iterdir():
                if f.is_file():
                    try:
                        f.unlink()
                    except OSError:
                        pass
            
            # 删除空目录
            if parent_dir != download_dir and not any(parent_dir.iterdir()):
                try:
                    parent_dir.rmdir()
                except OSError:
                    pass
            
            results.append({"filename": filename, "status": "deleted"})
            logger.info("批量删除: %s", filename)
        
        except HTTPException:
            results.append({"filename": filename, "status": "error", "reason": "非法文件名"})
        except Exception as e:
            results.append({"filename": filename, "status": "error", "reason": str(e)})
    
    success = sum(1 for r in results if r["status"] == "deleted")
    return {
        "status": "ok",
        "total": len(filenames),
        "success": success,
        "failed": len(filenames) - success,
        "results": results,
    }


@router.put("/videos/{filename:path}/tags")
async def update_video_tags(
    filename: str,
    request: Request,
    payload: dict = Depends(verify_admin_authorization),
) -> dict:
    """
    更新视频标签。
    
    请求体: {"tags": ["tag1", "tag2"]}
    """
    if payload["role"] == "readonly":
        raise HTTPException(status_code=403, detail="权限不足")

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
    payload: dict = Depends(verify_admin_authorization),
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
    import io
    
    def generate_zip():
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for filename in filenames:
                try:
                    filepath = _validate_filename(filename, download_dir)
                    if not filepath.is_file():
                        logger.warning("导出 ZIP 时文件不存在: %s", filename)
                        continue
                    
                    # 添加视频文件
                    zf.write(filepath, filename)
                    
                    # 添加元数据
                    meta_path = filepath.parent / "meta.json"
                    if meta_path.exists():
                        meta_name = f"{filepath.parent.name}/meta.json"
                        zf.write(meta_path, meta_name)
                    
                    # 添加缩略图（如果存在）
                    for f in filepath.parent.iterdir():
                        if f.is_file() and f.name.startswith("thumbnail"):
                            thumb_name = f"{filepath.parent.name}/{f.name}"
                            zf.write(f, thumb_name)
                
                except Exception as e:
                    logger.error("添加文件到 ZIP 失败 %s: %s", filename, e)
        
        buffer.seek(0)
        yield buffer.read()
    
    return StreamingResponse(
        generate_zip(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=\"gotube_export.zip\""},
    )


@router.post("/export/json")
async def export_json(
    request: Request,
    payload: dict = Depends(verify_admin_authorization),
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
    payload: dict = Depends(verify_admin_authorization),
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
    payload: dict = Depends(verify_admin_authorization),
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

