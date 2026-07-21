"""
多用户下载队列管理器

负责任务调度、并发控制、客户端连接管理。
"""

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path
from collections.abc import Callable

from .downloader import Downloader, DownloadTask
from .url_normalizer import normalize_media_url

logger = logging.getLogger(__name__)


class QueueManager:
    """下载队列管理器"""

    def __init__(self, downloader: Downloader, max_concurrent: int = 5, max_downloads_per_user: int = 1) -> None:
        """
        初始化队列管理器。

        Args:
            downloader: 下载器实例。
            max_concurrent: 最大并发下载数。
            max_downloads_per_user: 单用户最大同时下载数（0=不限制）。
        """
        self.downloader = downloader
        self.max_concurrent = max_concurrent
        self.max_downloads_per_user = max_downloads_per_user
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._user_semaphores: dict[str, asyncio.Semaphore] = {}
        self._progress_callbacks: dict[str, Callable] = {}
        self._running_tasks: dict[str, asyncio.Task] = {}

    def register_client(self, client_id: str, progress_callback: Callable) -> None:
        """
        注册客户端（WebSocket 连接时调用）。

        Args:
            client_id: 客户端标识。
            progress_callback: 异步进度回调函数。
        """
        self._progress_callbacks[client_id] = progress_callback
        logger.info("客户端已注册: %s", client_id)

    def unregister_client(self, client_id: str) -> None:
        """
        注销客户端。

        Args:
            client_id: 客户端标识。
        """
        self._progress_callbacks.pop(client_id, None)
        logger.info("客户端已注销: %s", client_id)

    async def add_task(
        self,
        url: str,
        client_id: str,
        session_id: str | None = None,
        owner_user_id: int | None = None,
        source_url: str | None = None,
    ) -> DownloadTask | None:
        """
        添加下载任务并启动下载（受信号量控制并发）。

        同一客户端的相同 URL 如果已有非失败/非取消状态的任务，则返回已有任务。

        Args:
            url: 视频链接。
            client_id: 客户端标识。
            session_id: 匿名用户会话 ID（可选）。

        Returns:
            新创建或已有的 DownloadTask 对象，如果URL重复且不可重试则返回None。
        """
        # 检查同客户端是否有相同URL的非失败任务
        source_url = source_url or normalize_media_url(url).canonical_url or url
        existing = self._find_task_by_url(client_id, source_url)
        if existing is not None:
            logger.info("URL重复，返回已有任务: %s, url=%s", existing.task_id, url[:80])
            return existing

        task = self.downloader.create_task(url, client_id)
        task.source_url = source_url
        task.original_url = url
        task.owner_user_id = owner_user_id

        # 设置 guest 标识
        if session_id:
            task.is_guest = True
            task.session_id = session_id

        # 启动下载（受信号量控制并发数）
        runner = asyncio.create_task(self._execute_with_semaphore(task), name=f"download-{task.task_id}")
        self._running_tasks[task.task_id] = runner
        runner.add_done_callback(lambda _runner, task_id=task.task_id: self._running_tasks.pop(task_id, None))

        logger.info("任务已加入队列: %s, client=%s, is_guest=%s", task.task_id, client_id, bool(session_id))
        return task

    def add_completed_library_task(self, url: str, client_id: str, item, asset) -> DownloadTask:
        """Create a completed in-memory task for a reused library item."""
        task = self.downloader.create_task(url, client_id)
        task.source_url = normalize_media_url(url).canonical_url or url
        task.original_url = url
        task.status = "completed"
        task.progress = 100.0
        task.completed_at = datetime.now(UTC)
        task.filename = asset.filename
        task.filepath = asset.filepath
        task.title = item.display_title or asset.title
        task.thumbnail = asset.thumbnail
        task.duration = asset.duration or 0
        task.file_hash = asset.file_hash
        task.is_duplicate = True
        task.owner_user_id = item.owner_user_id
        task.user_video_item_id = item.id
        task.media_asset_id = asset.id
        task.share_token = item.share_token
        logger.info("复用已有媒体资产创建完成任务: %s, asset=%s, item=%s", task.task_id, asset.id, item.id)
        return task

    def add_completed_guest_asset_task(self, url: str, client_id: str, session_id: str, asset) -> DownloadTask:
        """Create a completed guest task for an existing library asset."""
        task = self.downloader.create_task(url, client_id)
        task.source_url = normalize_media_url(url).canonical_url or url
        task.original_url = url
        task.status = "completed"
        task.progress = 100.0
        task.completed_at = datetime.now(UTC)
        task.filename = f"temp_guest/{session_id}/DUPLICATE/{asset.filename}"
        task.filepath = asset.filepath
        task.title = asset.title
        task.thumbnail = asset.thumbnail
        task.duration = asset.duration or 0
        task.file_hash = asset.file_hash
        task.is_duplicate = True
        task.is_guest = True
        task.session_id = session_id
        task.media_asset_id = asset.id
        logger.info("复用已有媒体资产创建游客任务: %s, asset=%s, session=%s", task.task_id, asset.id, session_id)
        return task

    def _find_task_by_url(self, client_id: str, source_url: str) -> DownloadTask | None:
        """
        查找同客户端下相同URL的非失败任务。

        可重试状态（failed）返回None，允许重新下载。

        Args:
            client_id: 客户端标识。
            url: 视频链接。

        Returns:
            匹配的非失败任务，未找到返回None。
        """
        retryable = {"failed"}
        for task in self.downloader.get_tasks_by_client(client_id):
            task_source_url = getattr(task, "source_url", "") or normalize_media_url(task.url).canonical_url or task.url
            if task_source_url == source_url and task.status not in retryable:
                return task
        return None

    def get_active_tasks_for_client(self, client_id: str) -> list[DownloadTask]:
        """获取指定 client 的 pending/downloading 任务。"""
        return [
            task
            for task in self.downloader.get_tasks_by_client(client_id)
            if task.status in ("pending", "downloading")
        ]

    def get_active_tasks_for_guest_session(self, session_id: str) -> list[DownloadTask]:
        """获取指定 guest session 的 pending/downloading 任务。"""
        return [
            task
            for task in self.downloader.get_active_tasks()
            if task.is_guest and task.session_id == session_id
        ]

    def get_active_tasks_for_owner(self, owner_user_id: int) -> list[DownloadTask]:
        """获取指定登录用户的 pending/downloading 任务。"""
        return [
            task
            for task in self.downloader.get_active_tasks()
            if task.owner_user_id == owner_user_id and not task.is_guest
        ]

    def cancel_task(self, task_id: str, client_id: str | None = None, reason: str = "下载已取消") -> bool:
        """取消一个 pending/downloading 任务。"""
        task = self.downloader.get_task(task_id)
        if not task:
            return False
        if client_id is not None and task.client_id != client_id:
            return False
        if task.status not in ("pending", "downloading"):
            return False

        was_pending = task.status == "pending"
        task.request_cancel(reason)
        task.status = "cancelled"
        task.error = task.cancel_reason
        task.completed_at = datetime.now(UTC)

        runner = self._running_tasks.get(task_id)
        if was_pending and runner and not runner.done():
            runner.cancel()

        self.downloader.cleanup_download_artifacts(task)
        self.downloader.cleanup_temp_files(task.task_id)
        logger.info("已取消下载任务: task=%s, client=%s, reason=%s", task_id, task.client_id, task.error)
        return True

    def cancel_client_tasks(self, client_id: str, reason: str = "下载已取消") -> int:
        """取消指定 client 的所有活跃任务。"""
        return sum(
            1
            for task in list(self.get_active_tasks_for_client(client_id))
            if self.cancel_task(task.task_id, client_id=client_id, reason=reason)
        )

    def cancel_guest_session_tasks(self, session_id: str, reason: str = "游客会话已关闭") -> int:
        """取消指定 guest session 的所有活跃任务。"""
        return sum(
            1
            for task in list(self.get_active_tasks_for_guest_session(session_id))
            if self.cancel_task(task.task_id, reason=reason)
        )

    @staticmethod
    def _user_key(task: DownloadTask) -> str | None:
        """从任务推导用户标识：登录用户按账号，游客按会话。"""
        if task.is_guest and task.session_id:
            return f"guest:{task.session_id}"
        if task.owner_user_id is not None:
            return f"user:{task.owner_user_id}"
        return None

    def _resolve_user_semaphore(self, task: DownloadTask) -> asyncio.Semaphore | None:
        """获取任务对应的单用户信号量，不限制时返回 None。"""
        if self.max_downloads_per_user <= 0:
            return None
        key = self._user_key(task)
        if key is None:
            return None
        if key not in self._user_semaphores:
            self._user_semaphores[key] = asyncio.Semaphore(self.max_downloads_per_user)
        return self._user_semaphores[key]

    async def _execute_with_semaphore(self, task: DownloadTask) -> None:
        """使用信号量控制并发执行下载（单用户 + 全局）"""
        try:
            user_sem = self._resolve_user_semaphore(task)
            if user_sem is not None:
                async with user_sem:
                    await self._download_with_global_semaphore(task)
            else:
                await self._download_with_global_semaphore(task)
        except asyncio.CancelledError:
            logger.info("下载任务 runner 已取消: task=%s", task.task_id)

    async def _download_with_global_semaphore(self, task: DownloadTask) -> None:
        """获取全局信号量后执行下载。"""
        async with self._semaphore:
            if task.cancel_requested:
                return
            callback = self._build_callback(task.client_id)
            await self.downloader.download(task, callback)
            if task.status == "completed" and task.owner_user_id and not task.is_guest:
                self._register_completed_library_item(task)
                await callback(task)

    def _register_completed_library_item(self, task: DownloadTask) -> None:
        """Persist completed logged-in downloads into the v4 video library."""
        if not task.filepath:
            return
        from .db import get_session
        from .video_library import register_completed_file

        with get_session() as session:
            try:
                item = register_completed_file(
                    session,
                    owner_user_id=task.owner_user_id,
                    filepath=Path(task.filepath),
                    download_dir=self.downloader.download_dir,
                    source_url=task.source_url,
                    title=task.title,
                    file_hash=task.file_hash,
                    thumbnail=task.thumbnail,
                    duration=task.duration,
                    meta={
                        "url": task.source_url,
                        "original_url": task.original_url,
                        "title": task.title,
                        "thumbnail": task.thumbnail,
                        "video_id": task.video_id,
                        "duration": task.duration,
                        "file_hash": task.file_hash,
                    },
                )
                session.commit()
                task.user_video_item_id = item.id
                task.media_asset_id = item.media_asset_id
                task.share_token = item.share_token
            except Exception as exc:
                session.rollback()
                task.status = "failed"
                task.error = str(exc)
                if not task.is_duplicate:
                    self._delete_failed_library_download(task)
                logger.error("注册用户视频库条目失败: task=%s, error=%s", task.task_id, exc)

    def _delete_failed_library_download(self, task: DownloadTask) -> None:
        """Remove a newly downloaded file that could not be registered to a user's library."""
        if not task.filepath:
            return
        path = Path(task.filepath)
        try:
            if path.is_file():
                parent = path.parent
                path.unlink()
                if parent != self.downloader.download_dir and parent.exists():
                    import shutil

                    shutil.rmtree(parent)
                self.downloader.invalidate_file_index_cache()
                self.downloader.invalidate_hash_index()
                logger.info("已删除未入库下载文件: task=%s path=%s", task.task_id, path)
        except OSError as exc:
            logger.warning("删除未入库下载文件失败: task=%s path=%s error=%s", task.task_id, path, exc)

    def _build_callback(self, client_id: str) -> Callable:
        """构建进度回调函数"""

        async def callback(task: DownloadTask) -> None:
            cb = self._progress_callbacks.get(client_id)
            if cb:
                await cb(task)
            else:
                logger.debug(
                    "未找到客户端 %s 的进度回调，任务 %s 状态: %s",
                    client_id,
                    task.task_id,
                    task.status,
                )

        return callback

    def get_client_tasks(self, client_id: str) -> list[DownloadTask]:
        """
        获取指定客户端的所有任务。

        直接从 downloader._tasks 中按 client_id 过滤，
        不依赖 _client_tasks 映射（该映射会在 WebSocket 断开时被清空）。

        Args:
            client_id: 客户端标识。

        Returns:
            DownloadTask 列表。
        """
        return self.downloader.get_tasks_by_client(client_id)

    def retry_task(self, task_id: str, client_id: str) -> bool:
        """
        重试失败的任务（只能重试自己的任务）。

        只有 failed 状态的任务可以重试。

        Args:
            task_id: 任务 ID。
            client_id: 客户端标识。

        Returns:
            是否成功触发重试。
        """
        task = self.downloader.get_task(task_id)
        if not task or task.client_id != client_id:
            return False
        if task.status != "failed":
            return False

        # 重置状态后通过信号量调度，避免绕过并发限制
        self.downloader.reset_for_retry(task)
        runner = asyncio.create_task(self._execute_with_semaphore(task), name=f"retry-{task.task_id}")
        self._running_tasks[task.task_id] = runner
        runner.add_done_callback(lambda _runner, tid=task.task_id: self._running_tasks.pop(tid, None))
        logger.info("任务重试: %s, client=%s, url=%s", task_id, client_id, task.url[:80])
        return True

    def delete_task(self, task_id: str, client_id: str) -> bool:
        """
        删除任务记录（只能删除自己的任务）。

        Args:
            task_id: 任务 ID。
            client_id: 客户端标识。

        Returns:
            是否成功删除。
        """
        task = self.downloader.get_task(task_id)
        if not task or task.client_id != client_id:
            return False

        return self.downloader.delete_task(task_id)

    def get_active_count(self) -> int:
        """获取当前活跃的下载任务数"""
        return self.downloader.count_by_status("downloading")

    def get_queue_count(self) -> int:
        """获取排队中的任务数"""
        return self.downloader.count_by_status("pending")

    async def shutdown(self) -> None:
        """
        优雅关闭：记录活跃任务日志，等待自然结束。

        由于不支持取消功能，关闭时只记录日志并等待。
        """
        active = self.downloader.get_active_tasks()
        if not active:
            logger.info("关闭 QueueManager: 无活跃任务")
            return

        logger.info("关闭 QueueManager: 有 %d 个活跃任务将在进程退出后自然结束", len(active))
