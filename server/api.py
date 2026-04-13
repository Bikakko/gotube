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

from .downloader import VIDEO_EXTENSIONS, _read_meta_from_dir
from .models import AddTaskRequest, DeleteDownloadResponse, TaskResponse
from .queue_manager import QueueManager

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

    task = await qm.add_task(req.url, client_id)
    if task is None:
        # 同客户端相同URL且不可重试
        raise HTTPException(status_code=409, detail="该链接已在下载中或已完成，请勿重复提交")

    logger.info("添加任务: %s, client=%s", task.task_id, client_id)
    return _task_to_response(task)


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
async def list_downloads(qm: QueueManager = Depends(get_queue_manager)):
    """列出所有已下载的文件（含元数据，使用缓存索引）"""
    files = qm.downloader._build_file_index_cache()
    # 按修改时间倒序
    files.sort(key=lambda x: x["modified"], reverse=True)
    # 解析缩略图路径（兼容老数据远程 URL 和新数据本地文件）
    for f in files:
        if "thumbnail" in f and "file_hash" in f and f.get("filepath"):
            video_dir = Path(f["filepath"]).parent
            f["thumbnail"] = _resolve_thumbnail(f["thumbnail"], video_dir, f["file_hash"])
    return files


@router.get("/downloads/stream/{filename:path}")
async def stream_video(
    filename: str,
    qm: QueueManager = Depends(get_queue_manager),
):
    """视频文件下载"""
    download_dir = qm.downloader.download_dir
    filepath = download_dir / filename

    logger.info("[/api/downloads/stream] request filename=%s, resolved path=%s", filename, filepath)

    # 防止路径遍历攻击
    try:
        filepath.resolve().relative_to(download_dir.resolve())
    except ValueError as e:
        logger.warning("[/api/downloads/stream] illegal path: %s, error=%s", filepath, e)
        raise HTTPException(status_code=403, detail="非法文件路径") from e

    if not filepath.is_file():
        logger.warning("[/api/downloads/stream] file not found: %s", filepath)
        raise HTTPException(status_code=404, detail="文件不存在")

    logger.info("[/api/downloads/stream] returning video: path=%s, size=%d", filepath, filepath.stat().st_size)
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
    download_dir = qm.downloader.download_dir

    # 使用 hash 索引查找
    hash_index = qm.downloader._build_hash_index()
    matched_file: Path | None = None
    for h, fp in hash_index.items():
        if h.startswith(hash_id) or hash_id.startswith(h):
            matched_file = fp
            break

    if matched_file is None:
        # 降级到递归扫描
        for f in download_dir.rglob(f"{hash_id}*"):
            if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS:
                matched_file = f
                break

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
    download_dir = qm.downloader.download_dir

    # 使用 hash 索引查找
    hash_index = qm.downloader._build_hash_index()
    matched_file: Path | None = None
    for h, fp in hash_index.items():
        if h.startswith(hash_id) or hash_id.startswith(h):
            matched_file = fp
            break

    if matched_file is None:
        # 降级到递归扫描
        for f in download_dir.rglob(f"{hash_id}*"):
            if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS:
                matched_file = f
                break

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
async def delete_download(
    filename: str,
    qm: QueueManager = Depends(get_queue_manager),
):
    """
    删除已下载的视频文件（含物理删除）。

    会删除视频文件和同目录下的 meta.json。
    """
    download_dir = qm.downloader.download_dir
    filepath = download_dir / filename

    # 防止路径遍历攻击
    try:
        filepath.resolve().relative_to(download_dir.resolve())
    except ValueError as e:
        raise HTTPException(status_code=403, detail="非法文件路径") from e

    if not filepath.is_file():
        raise HTTPException(status_code=404, detail="文件不存在") from None

    deleted_files: list[str] = []
    parent_dir = filepath.parent

    # 删除视频文件
    try:
        filepath.unlink()
        deleted_files.append(str(filepath.relative_to(download_dir)))
        logger.info("已删除视频文件: %s", filepath)
    except OSError as e:
        logger.error("删除视频文件失败: %s, 错误: %s", filepath, e)
        raise HTTPException(status_code=500, detail=f"删除文件失败: {e}") from e

    # 删除同目录下的 meta.json（如果该目录下没有其他视频文件）
    meta_path = parent_dir / "meta.json"
    if meta_path.exists():
        try:
            meta_path.unlink()
            deleted_files.append(str(meta_path.relative_to(download_dir)))
            logger.info("已删除元数据: %s", meta_path)
        except OSError as e:
            logger.warning("删除元数据失败 %s: %s", meta_path, e)

    # 如果目录下没有其他文件，删除目录
    try:
        if parent_dir != download_dir and not any(parent_dir.iterdir()):
            parent_dir.rmdir()
            deleted_files.append(str(parent_dir.relative_to(download_dir)) + "/")
            logger.info("已删除空目录: %s", parent_dir)
    except OSError as e:
        logger.warning("删除空目录失败 %s: %s", parent_dir, e)

    # 刷新缓存，避免 hash 索引中残留已删除文件的引用
    try:
        qm.downloader.invalidate_file_index_cache()
        qm.downloader.invalidate_hash_index()
        logger.info("删除视频后已刷新缓存")
    except Exception as e:
        logger.warning("删除视频后刷新缓存失败: %s", e)

    return DeleteDownloadResponse(status="ok", deleted_files=deleted_files)
