"""GoTube Desktop entrypoint."""

from __future__ import annotations

import os
import inspect
import threading
from pathlib import Path
from typing import Callable

from .core.config import DesktopConfig, DesktopConfigStore
from .core.cookies import DesktopCookieStore
from .core.downloader import DesktopDownloader
from .core.logs import DesktopLogStore
from .core.tasks import DesktopTask
from .core.tools import detect_ffmpeg, detect_ytdlp, upgrade_ytdlp


class DesktopApi:
    def __init__(
        self,
        *,
        config_store: DesktopConfigStore | None = None,
        downloader_factory: Callable[[DesktopConfig], DesktopDownloader] | None = None,
        folder_opener: Callable[[Path], None] | None = None,
    ) -> None:
        self.config_store = config_store or DesktopConfigStore()
        self.config = self.config_store.load()
        self.cookie_store = DesktopCookieStore(self.config_store.config_dir)
        self.log_store = DesktopLogStore(self.config_store.config_dir / "desktop.log")
        self.downloader_factory = downloader_factory or self._create_downloader
        self.folder_opener = folder_opener or self._open_folder
        self.tasks: list[DesktopTask] = []
        self.canceled_task_ids: set[str] = set()
        self._lock = threading.Lock()

    def get_config(self) -> dict:
        return {
            "download_dir": str(self.config.download_dir),
            "cookies_file": str(self.config.cookies_file) if self.config.cookies_file else "",
            "ffmpeg_path": str(self.config.ffmpeg_path) if self.config.ffmpeg_path else "",
            "browser_cookie_source": self.config.browser_cookie_source or "",
        }

    def get_app_info(self) -> dict:
        version_file = Path(__file__).resolve().parents[1] / "VERSION"
        try:
            version = version_file.read_text(encoding="utf-8").strip()
        except OSError:
            version = "unknown"
        return {"name": "GoTube Desktop", "version": version or "unknown"}

    def set_download_dir(self, path: str) -> dict:
        clean_path = path.strip()
        if not clean_path:
            return {"ok": False, "message": "保存位置不能为空", **self.get_config()}
        self.config.download_dir = Path(clean_path)
        self.config_store.save(self.config)
        return {"ok": True, "message": "保存位置已更新", **self.get_config()}

    def set_ffmpeg_path(self, path: str) -> dict:
        self.config.ffmpeg_path = Path(path) if path else None
        self.config_store.save(self.config)
        return self.get_config()

    def open_download_dir(self) -> dict:
        self.config.download_dir.mkdir(parents=True, exist_ok=True)
        self.folder_opener(self.config.download_dir)
        return {"ok": True, "path": str(self.config.download_dir)}

    def open_task_location(self, task_id: str) -> dict:
        with self._lock:
            task = next((item for item in self.tasks if item.id == task_id), None)
        if task is None:
            return {"ok": False, "message": "任务不存在"}
        if task.status != "completed" or not task.file_path:
            return {"ok": False, "message": "任务尚未完成"}

        folder = Path(task.file_path).parent
        folder.mkdir(parents=True, exist_ok=True)
        self.folder_opener(folder)
        return {"ok": True, "message": "已打开文件位置", "path": str(folder)}

    def save_cookie(self, content: str) -> dict:
        result = self.cookie_store.save_manual_cookie(content)
        if result.ok:
            self.config.cookies_file = result.path
            self.config_store.save(self.config)
        return {"ok": result.ok, "message": result.message}

    def delete_cookie(self) -> dict:
        result = self.cookie_store.delete_cookie_file()
        if result.ok:
            self.config.cookies_file = None
            self.config_store.save(self.config)
            self.log_store.append("Cookie 已删除")
        return {"ok": result.ok, "message": result.message}

    def import_browser_cookie(self, browser: str) -> dict:
        result = self.cookie_store.import_from_browser(browser)
        if result.ok:
            self.config.browser_cookie_source = browser.strip().lower()
            self.config_store.save(self.config)
            self.log_store.append(f"浏览器 Cookie 来源已设置：{self.config.browser_cookie_source}")
        return {"ok": result.ok, "message": result.message}

    def detect_tools(self) -> dict:
        ffmpeg = detect_ffmpeg(configured_path=self.config.ffmpeg_path)
        ytdlp = detect_ytdlp()
        return {
            "ffmpeg": _tool_to_dict(ffmpeg),
            "yt_dlp": _tool_to_dict(ytdlp),
        }

    def upgrade_ytdlp(self) -> dict:
        result = upgrade_ytdlp()
        return {
            "ok": result.ok,
            "message": result.message,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    def create_download(self, url: str) -> dict:
        task = DesktopTask.create(url=url)
        with self._lock:
            self.tasks.append(task)
        self.log_store.append(f"下载任务已创建：{url}")

        def run() -> None:
            with self._lock:
                if task.id in self.canceled_task_ids:
                    return
                task.mark_running()
            downloader = self.downloader_factory(self.config)

            def on_progress(progress_task: DesktopTask) -> None:
                with self._lock:
                    if task.id in self.canceled_task_ids:
                        return
                    _copy_task_state(target=task, source=progress_task)

            try:
                finished_task = _download_with_supported_args(
                    downloader,
                    url,
                    on_progress=on_progress,
                    should_cancel=lambda: task.id in self.canceled_task_ids,
                )
                with self._lock:
                    if task.id in self.canceled_task_ids:
                        task.mark_canceled()
                        self.log_store.append(f"下载任务已取消：{url}")
                        removed = _cleanup_partial_downloads(downloader)
                        if removed:
                            self.log_store.append(f"已清理临时文件：{removed}")
                        return
                    _copy_task_state(target=task, source=finished_task)
                if task.status == "completed":
                    self.log_store.append(f"下载任务已完成：{url}")
                elif task.status == "canceled":
                    self.log_store.append(f"下载任务已取消：{url}")
                else:
                    self.log_store.append(f"下载任务失败：{url}，{task.error}")
            except Exception as exc:
                task.mark_failed(str(exc))
                self.log_store.append(f"下载任务失败：{url}，{exc}")

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return {"ok": True, "message": "下载任务已开始", "task_id": task.id}

    def cancel_task(self, task_id: str) -> dict:
        with self._lock:
            for task in self.tasks:
                if task.id == task_id:
                    if task.status in {"completed", "failed", "canceled"}:
                        return {"ok": False, "message": "任务已经结束"}
                    self.canceled_task_ids.add(task_id)
                    task.mark_canceled()
                    self.log_store.append(f"下载任务已取消：{task.url}")
                    return {"ok": True, "message": "任务已取消"}
        return {"ok": False, "message": "任务不存在"}

    def clear_finished_tasks(self) -> dict:
        finished_statuses = {"completed", "failed", "canceled"}
        with self._lock:
            before = len(self.tasks)
            self.tasks = [task for task in self.tasks if task.status not in finished_statuses]
            removed = before - len(self.tasks)
        if removed:
            self.log_store.append(f"已清理任务记录：{removed}")
        return {"ok": True, "message": f"已清理 {removed} 个任务", "removed": removed}

    def get_tasks(self) -> list[dict]:
        with self._lock:
            tasks = list(self.tasks)
        return [
            {
                "id": task.id,
                "url": task.url,
                "status": task.status,
                "percent": task.percent,
                "speed": task.speed,
                "eta": task.eta,
                "file_path": task.file_path,
                "error": task.error,
            }
            for task in tasks
        ]

    def get_logs(self) -> dict:
        return {"lines": self.log_store.read_recent()}

    def _create_downloader(self, config: DesktopConfig) -> DesktopDownloader:
        return DesktopDownloader(
            download_dir=config.download_dir,
            cookies_file=config.cookies_file,
            browser_cookie_source=config.browser_cookie_source,
            ffmpeg_path=config.ffmpeg_path,
        )

    def _open_folder(self, path: Path) -> None:
        os.startfile(path)  # type: ignore[attr-defined]


def _tool_to_dict(status) -> dict:
    return {
        "name": status.name,
        "available": status.available,
        "version": status.version,
        "path": str(status.path) if status.path else "",
        "source": status.source,
        "message": status.message,
    }


def _copy_task_state(*, target: DesktopTask, source: DesktopTask) -> None:
    target.status = source.status
    target.percent = source.percent
    target.speed = source.speed
    target.eta = source.eta
    target.file_path = source.file_path
    target.error = source.error
    target.updated_at = source.updated_at


def _download_with_supported_args(
    downloader,
    url: str,
    *,
    on_progress,
    should_cancel,
) -> DesktopTask:
    params = inspect.signature(downloader.download).parameters
    kwargs = {"on_progress": on_progress}
    if "should_cancel" in params:
        kwargs["should_cancel"] = should_cancel
    return downloader.download(url, **kwargs)


def _cleanup_partial_downloads(downloader) -> int:
    cleanup = getattr(downloader, "cleanup_partial_downloads", None)
    if not callable(cleanup):
        return 0
    return int(cleanup() or 0)


def main() -> None:
    try:
        import webview
    except ImportError as exc:
        raise SystemExit("缺少 pywebview，请先安装桌面版依赖。") from exc

    api = DesktopApi()
    ui_path = Path(__file__).parent / "ui" / "index.html"
    webview.create_window(
        "GoTube Desktop",
        ui_path.as_uri(),
        js_api=api,
        width=1180,
        height=760,
    )
    webview.start()


if __name__ == "__main__":
    os.environ.setdefault("PYWEBVIEW_LOG", "debug")
    main()
