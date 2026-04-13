"""
多用户下载队列管理器

负责任务调度、并发控制、客户端连接管理。
"""

import asyncio
import logging
from collections.abc import Callable

from .downloader import Downloader, DownloadTask

logger = logging.getLogger(__name__)


class QueueManager:
    """下载队列管理器"""

    def __init__(self, downloader: Downloader, max_concurrent: int = 5) -> None:
        """
        初始化队列管理器。

        Args:
            downloader: 下载器实例。
            max_concurrent: 最大并发下载数。
        """
        self.downloader = downloader
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._progress_callbacks: dict[str, Callable] = {}

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

    async def add_task(self, url: str, client_id: str) -> DownloadTask | None:
        """
        添加下载任务并启动下载（受信号量控制并发）。

        同一客户端的相同 URL 如果已有非失败/非取消状态的任务，则返回已有任务。

        Args:
            url: 视频链接。
            client_id: 客户端标识。

        Returns:
            新创建或已有的 DownloadTask 对象，如果URL重复且不可重试则返回None。
        """
        # 检查同客户端是否有相同URL的非失败任务
        existing = self._find_task_by_url(client_id, url)
        if existing is not None:
            logger.info("URL重复，返回已有任务: %s, url=%s", existing.task_id, url[:80])
            return existing

        task = self.downloader.create_task(url, client_id)

        # 启动下载（受信号量控制并发数）
        asyncio.create_task(self._execute_with_semaphore(task), name=f"download-{task.task_id}")

        logger.info("任务已加入队列: %s, client=%s", task.task_id, client_id)
        return task

    def _find_task_by_url(self, client_id: str, url: str) -> DownloadTask | None:
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
            if task.url == url and task.status not in retryable:
                return task
        return None

    async def _execute_with_semaphore(self, task: DownloadTask) -> None:
        """使用信号量控制并发执行下载"""
        async with self._semaphore:
            callback = self._build_callback(task.client_id)
            await self.downloader.download(task, callback)

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

        # 构建回调并启动重试
        callback = self._build_callback(client_id)
        self.downloader.retry_task(task, callback)
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
