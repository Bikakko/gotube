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

from .admin_api import verify_admin_authorization
from .downloader import _read_meta_from_dir
from .models import AddTaskRequest, TaskResponse
from .path_utils import resolve_inside
from .queue_manager import QueueManager
from .config import settings
from .security import validate_guest_session_id, validate_hash_id

logger = logging.getLogger(__name__)

router = APIRouter()


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
        created_at=task.created_at.isoformat(),
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
    )


# ── 任务管理 API ──


@router.post("/tasks", response_model=TaskResponse)
async def add_task(
    req: AddTaskRequest,
    client_id: str = Query(..., description="客户端标识"),
    qm: QueueManager = Depends(get_queue_manager),
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

    # 检查是否为匿名用户（未登录用户传递 session_id，登录用户不传）
    is_guest = bool(req.session_id)
    if is_guest and not settings.allow_guest_download:
        raise HTTPException(status_code=403, detail="匿名用户下载功能已禁用")
    if is_guest:
        req.session_id = validate_guest_session_id(req.session_id)

    task = await qm.add_task(req.url, client_id, session_id=req.session_id)
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
    payload: dict = Depends(verify_admin_authorization),
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
