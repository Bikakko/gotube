"""
REST API 路由

提供任务管理、文件查询、视频删除等接口。
通过 app.state 注入 QueueManager，避免全局可变状态。
"""

import logging
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .auth import get_current_user, get_db, get_optional_current_user
from .db import User
from .downloader import _read_meta_from_dir
from .invites import register_user_with_invite
from .models import AddTaskRequest, RegisterRequest, TaskResponse, UpdateShareRequest
from .path_utils import resolve_inside
from .quota import get_effective_quota_bytes, refresh_user_storage_usage
from .queue_manager import QueueManager
from .config import settings
from .security import validate_guest_session_id, validate_hash_id
from .video_library import (
    create_item_from_existing_source,
    delete_user_video_item,
    get_user_video_asset_for_download,
    list_user_video_items,
    resolve_share_token,
    set_user_video_share_enabled,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/auth/register")
async def register(
    body: RegisterRequest,
    db: Session = Depends(get_db),
) -> dict:
    """公开注册接口：必须提供有效邀请码，只创建普通用户。"""
    user = register_user_with_invite(
        db,
        username=body.username,
        password=body.password,
        invite_code=body.invite_code,
    )
    db.commit()
    return {
        "success": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
        },
    }


# ── URL 验证 ──


def _validate_url_format(url: str) -> None:
    """
    验证 URL 格式是否合法。

    必须是 http:// 或 https:// 协议，且有有效的主机名。

    Raises:
        HTTPException: 如果 URL 格式不合法。
    """
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise HTTPException(status_code=400, detail="URL 格式无效") from e

    if parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=400,
            detail="URL 必须使用 http:// 或 https:// 协议",
        )

    if not parsed.hostname:
        raise HTTPException(status_code=400, detail="URL 缺少主机名")


# ── 依赖注入 ──


def get_queue_manager(request: Request) -> QueueManager:
    """从 app.state 获取 queue_manager 实例"""
    qm: QueueManager | None = getattr(request.app.state, "queue_manager", None)
    if qm is None:
        raise HTTPException(status_code=500, detail="服务未初始化")
    return qm


# ── 辅助函数 ──


def _resolve_thumbnail(thumbnail: str, video_dir: Path, hash_id: str) -> str:
    """
    解析缩略图路径：如果是本地文件则返回 API URL，否则返回原始远程 URL。

    兼容老数据（远程 URL）和新数据（本地相对路径）。

    Args:
        thumbnail: meta.json 中的 thumbnail 字段值。
        video_dir: 视频所在目录的绝对路径。
        hash_id: 视频 hash ID。

    Returns:
        可访问的缩略图 URL。
    """
    if not thumbnail:
        return ""
    # 远程 URL（老数据）直接返回
    if thumbnail.startswith(("http://", "https://")):
        return thumbnail
    # 本地相对路径，转换为 API URL
    local_path = video_dir / thumbnail
    if local_path.is_file():
        return f"/api/thumbnail/{hash_id}"
    # 文件不存在，降级返回原始值
    return thumbnail


def _task_to_response(task) -> TaskResponse:
    """将 DownloadTask 转换为 TaskResponse"""
    return TaskResponse(
        task_id=task.task_id,
        url=task.url,
        status=task.status,
        progress=task.progress,
        speed=task.speed,
        eta=task.eta,
        filename=task.filename,
        error=task.error,
        title=task.title,
        thumbnail=task.thumbnail,
        duration=task.duration,
        video_id=task.video_id,
        file_hash=task.file_hash,
        is_duplicate=task.is_duplicate,
        user_video_item_id=getattr(task, "user_video_item_id", None),
        media_asset_id=getattr(task, "media_asset_id", None),
        share_token=getattr(task, "share_token", ""),
        created_at=task.created_at.isoformat(),
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
    )


# ── 任务管理 API ──


@router.post("/tasks", response_model=TaskResponse)
async def add_task(
    req: AddTaskRequest,
    client_id: str = Query(..., description="客户端标识"),
    qm: QueueManager = Depends(get_queue_manager),
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """添加下载任务"""
    if not req.url:
        raise HTTPException(status_code=400, detail="URL 不能为空")

    # 基础验证：排除纯中文、纯符号等无效输入
    import re
    if not re.search(r'[a-zA-Z0-9]', req.url):
        raise HTTPException(status_code=400, detail="请输入有效的视频链接地址")

    # 验证 URL 格式（必须 http/https 开头）
    _validate_url_format(req.url)

    # 未登录用户使用 guest session；登录用户进入个人视频库流程。
    is_guest = current_user is None and bool(req.session_id)
    if is_guest and not settings.allow_guest_download:
        raise HTTPException(status_code=403, detail="匿名用户下载功能已禁用")
    if is_guest:
        req.session_id = validate_guest_session_id(req.session_id)

    owner_user_id = current_user.id if current_user is not None else None
    if current_user is not None:
        quota = get_effective_quota_bytes(current_user)
        used = refresh_user_storage_usage(db, current_user.id)
        if quota is not None and used >= quota:
            raise HTTPException(status_code=403, detail="视频库容量已达上限")

        reused_item = create_item_from_existing_source(db, current_user.id, req.url)
        if reused_item is not None:
            from .db import MediaAsset

            db.commit()
            db.refresh(reused_item)
            asset = db.query(MediaAsset).filter(MediaAsset.id == reused_item.media_asset_id).one()
            task = qm.add_completed_library_task(req.url, client_id, reused_item, asset)
            logger.info("复用已有视频: task=%s, user=%s, item=%s", task.task_id, current_user.id, reused_item.id)
            return _task_to_response(task)

    task = await qm.add_task(
        req.url,
        client_id,
        session_id=req.session_id if is_guest else None,
        owner_user_id=owner_user_id,
    )
    if task is None:
        # 同客户端相同URL且不可重试
        raise HTTPException(status_code=409, detail="该链接已在下载中或已完成，请勿重复提交")

    logger.info("添加任务: %s, client=%s, is_guest=%s", task.task_id, client_id, is_guest)
    return _task_to_response(task)


@router.post("/guest-downloads/{session_id}/transfer")
async def transfer_guest_downloads(
    session_id: str,
    client_id: str = Query(..., description="客户端标识"),
    qm: QueueManager = Depends(get_queue_manager),
    current_user=Depends(get_current_user),
):
    """
    将游客临时视频转移到视频库。
    
    游客登录后调用，将指定 session_id 下所有已完成的视频转移到主下载目录。
    返回更新后的任务数据，前端可直接刷新。
    """
    session_id = validate_guest_session_id(session_id)
    try:
        result = qm.downloader.transfer_guest_session(session_id, client_id=client_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error("转移游客视频失败: %s, 错误: %s", session_id, e)
        raise HTTPException(status_code=500, detail=f"转移失败: {str(e)}") from e


@router.get("/guest-downloads/{session_id}/count")
async def get_guest_download_count(
    session_id: str,
    qm: QueueManager = Depends(get_queue_manager),
):
    """
    获取游客 session 下的已完成视频数量。
    
    用于登录后判断是否需要提示转移。
    """
    session_id = validate_guest_session_id(session_id)
    count = qm.downloader.get_guest_download_count(session_id)
    return {"session_id": session_id, "count": count}


@router.get("/tasks", response_model=list[TaskResponse])
async def get_tasks(
    client_id: str = Query(..., description="客户端标识"),
    qm: QueueManager = Depends(get_queue_manager),
):
    """获取当前客户端的所有任务"""
    tasks = qm.get_client_tasks(client_id)
    return [_task_to_response(t) for t in tasks]


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: str,
    client_id: str = Query(..., description="客户端标识"),
    qm: QueueManager = Depends(get_queue_manager),
):
    """删除任务记录（只能删除自己的）"""
    if not qm.delete_task(task_id, client_id):
        raise HTTPException(status_code=404, detail="任务不存在或无权删除")
    return {"status": "ok"}


@router.get("/me/quota")
async def get_my_quota(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """返回当前用户的视频库容量状态。"""
    used = refresh_user_storage_usage(db, current_user.id)
    quota = get_effective_quota_bytes(current_user)
    db.commit()
    return {
        "role": current_user.role,
        "storage_used_bytes": used,
        "storage_quota_bytes": quota,
        "unlimited": quota is None,
        "over_quota": quota is not None and used >= quota,
    }


@router.get("/me/videos")
async def get_my_videos(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """返回当前登录用户的视频库。"""
    return {"videos": list_user_video_items(db, current_user)}


@router.delete("/me/videos/{item_id}")
async def delete_my_video(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """从当前用户视频库删除一个视频项。"""
    result = delete_user_video_item(db, current_user, item_id, settings.get_download_dir())
    db.commit()
    return result


@router.patch("/me/videos/{item_id}/share")
async def update_my_video_share(
    item_id: int,
    body: UpdateShareRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """开启或关闭当前用户视频库条目的分享链接。"""
    result = set_user_video_share_enabled(db, current_user, item_id, body.share_enabled)
    db.commit()
    return result


@router.get("/me/videos/{item_id}/download")
async def download_my_video(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    """下载当前用户自己的视频库条目，不按 filename 暴露主库路径。"""
    _item, asset = get_user_video_asset_for_download(db, current_user, item_id)
    path = Path(asset.filepath)
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=_download_filename(asset.title, path),
        content_disposition_type="attachment",
    )


@router.get("/me/videos/{item_id}/thumbnail")
async def get_my_video_thumbnail(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    """返回当前用户视频库条目的本地缩略图。"""
    _item, asset = get_user_video_asset_for_download(db, current_user, item_id)
    return _thumbnail_response(asset.thumbnail, Path(asset.filepath).parent)


@router.post("/tasks/{task_id}/retry")
async def retry_task(
    task_id: str,
    client_id: str = Query(..., description="客户端标识"),
    qm: QueueManager = Depends(get_queue_manager),
):
    """重试失败任务（只能重试自己的）"""
    if not qm.retry_task(task_id, client_id):
        raise HTTPException(status_code=404, detail="任务不存在或无法重试（仅失败任务可重试）")
    return {"status": "ok"}


# ── 下载文件管理 API ──


@router.get("/downloads")
async def list_downloads():
    """公开 API 不再暴露完整视频库列表。"""
    raise HTTPException(status_code=403, detail="请通过管理员接口访问视频列表")


@router.get("/downloads/stream/{filename:path}")
async def stream_video(filename: str):
    """公开 API 不再按文件名播放主视频库内容。"""
    raise HTTPException(status_code=403, detail="请通过分享链接播放视频")


@router.get("/guest-downloads/stream/{session_id}/{filename:path}")
async def stream_guest_video(
    session_id: str,
    filename: str,
    qm: QueueManager = Depends(get_queue_manager),
):
    """匿名用户视频文件下载（仅限自己的 session）"""
    session_id = validate_guest_session_id(session_id)
    download_dir = qm.downloader.guest_download_dir
    session_dir = resolve_inside(download_dir, session_id)
    filepath = resolve_inside(session_dir, filename)

    logger.info("[/api/guest-downloads/stream] request session=%s filename=%s, resolved path=%s", 
                session_id, filename, filepath)

    # 防止路径遍历攻击
    try:
        filepath.resolve().relative_to(session_dir.resolve())
    except ValueError as e:
        logger.warning("[/api/guest-downloads/stream] illegal path: %s, error=%s", filepath, e)
        raise HTTPException(status_code=403, detail="非法文件路径") from e

    if not filepath.is_file():
        logger.warning("[/api/guest-downloads/stream] file not found: %s", filepath)
        raise HTTPException(status_code=404, detail="文件不存在")

    logger.info("[/api/guest-downloads/stream] returning video: path=%s, size=%d", filepath, filepath.stat().st_size)
    return FileResponse(
        filepath,
        media_type="video/mp4",
        filename=filepath.name,
        headers={"Content-Disposition": f'inline; filename="{filepath.name}"'},
    )


@router.get("/share/{share_token}/info")
async def get_shared_video_info(
    share_token: str,
    db: Session = Depends(get_db),
) -> dict:
    """根据用户级分享 token 获取视频信息。"""
    resolved = resolve_share_token(db, share_token)
    if not resolved:
        raise HTTPException(status_code=404, detail="分享链接无效")
    item, asset = resolved
    path = Path(asset.filepath)
    stat = path.stat()
    return {
        "share_token": item.share_token,
        "filename": asset.filename,
        "size": stat.st_size,
        "modified": stat.st_mtime,
        "title": item.display_title or asset.title,
        "thumbnail": f"/api/share/{share_token}/thumbnail" if asset.thumbnail and not asset.thumbnail.startswith(("http://", "https://")) else asset.thumbnail,
        "duration": asset.duration or 0,
        "file_hash": asset.file_hash,
    }


@router.get("/share/{share_token}/thumbnail")
async def get_shared_thumbnail(
    share_token: str,
    db: Session = Depends(get_db),
):
    """返回分享视频的本地缩略图。"""
    resolved = resolve_share_token(db, share_token)
    if not resolved:
        raise HTTPException(status_code=404, detail="分享链接无效")
    _item, asset = resolved
    return _thumbnail_response(asset.thumbnail, Path(asset.filepath).parent)


@router.get("/share/{share_token}/download")
async def download_shared_video(
    share_token: str,
    db: Session = Depends(get_db),
) -> FileResponse:
    """下载分享视频，避免浏览器把 /watch 页面保存成无后缀 HTML。"""
    resolved = resolve_share_token(db, share_token)
    if not resolved:
        raise HTTPException(status_code=404, detail="分享链接无效")
    item, asset = resolved
    path = Path(asset.filepath)
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=_download_filename(item.display_title or asset.title, path),
        content_disposition_type="attachment",
    )


def _download_filename(title: str, path: Path) -> str:
    safe_title = "".join(c for c in (title or path.stem).strip() if c not in '<>:"/\\|?*').strip()
    if not safe_title:
        safe_title = path.stem
    suffix = path.suffix or ".mp4"
    if not safe_title.lower().endswith(suffix.lower()):
        safe_title += suffix
    return safe_title


def _thumbnail_response(thumbnail: str, video_dir: Path) -> FileResponse:
    thumb_name = thumbnail or ""
    if not thumb_name or thumb_name.startswith(("http://", "https://")):
        raise HTTPException(status_code=404, detail="缩略图不可用")

    thumb_path = video_dir / thumb_name
    if not thumb_path.is_file():
        raise HTTPException(status_code=404, detail="缩略图文件不存在")

    ext = thumb_path.suffix.lower()
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                ".webp": "image/webp", ".gif": "image/gif"}
    return FileResponse(thumb_path, media_type=mime_map.get(ext, "image/jpeg"))


@router.get("/video/{hash_id}/info")
async def get_video_info(
    hash_id: str,
    qm: QueueManager = Depends(get_queue_manager),
):
    """根据视频 hash ID 获取信息"""
    hash_id = validate_hash_id(hash_id)

    # 使用 hash 索引查找
    hash_index = qm.downloader._build_hash_index()
    matched_file: Path | None = hash_index.get(hash_id)

    if matched_file is not None and matched_file.is_file():
        stat = matched_file.stat()
        download_dir = qm.downloader.download_dir
        rel_path = matched_file.relative_to(download_dir)
        info: dict = {
            "hash_id": hash_id,
            "filename": str(rel_path),
            "size": stat.st_size,
            "modified": stat.st_mtime,
        }

        meta = _read_meta_from_dir(matched_file.parent)
        if meta:
            info["title"] = meta.get("title", "")
            info["thumbnail"] = _resolve_thumbnail(meta.get("thumbnail", ""), matched_file.parent, hash_id)
            info["video_id"] = meta.get("video_id", "")
            info["duration"] = meta.get("duration", 0)

        return info

    raise HTTPException(status_code=404, detail="视频不存在")


@router.get("/thumbnail/{hash_id}")
async def get_thumbnail(
    hash_id: str,
    qm: QueueManager = Depends(get_queue_manager),
):
    """获取视频的本地缩略图"""
    hash_id = validate_hash_id(hash_id)

    # 使用 hash 索引查找
    hash_index = qm.downloader._build_hash_index()
    matched_file: Path | None = hash_index.get(hash_id)

    if matched_file is None or not matched_file.is_file():
        raise HTTPException(status_code=404, detail="视频不存在")

    # 读取 meta.json 获取本地缩略图路径
    meta = _read_meta_from_dir(matched_file.parent)
    thumb_name = meta.get("thumbnail", "")
    if not thumb_name or thumb_name.startswith(("http://", "https://")):
        raise HTTPException(status_code=404, detail="缩略图不可用")

    thumb_path = matched_file.parent / thumb_name
    if not thumb_path.is_file():
        raise HTTPException(status_code=404, detail="缩略图文件不存在")

    # 根据扩展名确定 MIME 类型
    ext = thumb_path.suffix.lower()
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                ".webp": "image/webp", ".gif": "image/gif"}
    media_type = mime_map.get(ext, "image/jpeg")

    return FileResponse(thumb_path, media_type=media_type)


@router.delete("/downloads/{filename:path}")
async def delete_download(filename: str):
    """公开 API 不再允许按文件名删除主视频库内容。"""
    raise HTTPException(status_code=403, detail="请通过管理员接口删除视频")
