"""GoTube Desktop entrypoint."""

from __future__ import annotations

import os
import threading
from pathlib import Path

from .core.config import DesktopConfig, DesktopConfigStore
from .core.cookies import DesktopCookieStore
from .core.downloader import DesktopDownloader
from .core.tools import detect_ffmpeg, detect_ytdlp, upgrade_ytdlp


class DesktopApi:
    def __init__(self, *, config_store: DesktopConfigStore | None = None) -> None:
        self.config_store = config_store or DesktopConfigStore()
        self.config = self.config_store.load()
        self.cookie_store = DesktopCookieStore(self.config_store.config_dir)
        self.tasks = []

    def get_config(self) -> dict:
        return {
            "download_dir": str(self.config.download_dir),
            "cookies_file": str(self.config.cookies_file) if self.config.cookies_file else "",
            "ffmpeg_path": str(self.config.ffmpeg_path) if self.config.ffmpeg_path else "",
            "browser_cookie_source": self.config.browser_cookie_source or "",
        }

    def set_download_dir(self, path: str) -> dict:
        self.config.download_dir = Path(path)
        self.config_store.save(self.config)
        return self.get_config()

    def set_ffmpeg_path(self, path: str) -> dict:
        self.config.ffmpeg_path = Path(path) if path else None
        self.config_store.save(self.config)
        return self.get_config()

    def save_cookie(self, content: str) -> dict:
        result = self.cookie_store.save_manual_cookie(content)
        if result.ok:
            self.config.cookies_file = result.path
            self.config_store.save(self.config)
        return {"ok": result.ok, "message": result.message}

    def import_browser_cookie(self, browser: str) -> dict:
        result = self.cookie_store.import_from_browser(browser)
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
        downloader = DesktopDownloader(
            download_dir=self.config.download_dir,
            cookies_file=self.config.cookies_file,
            ffmpeg_path=self.config.ffmpeg_path,
        )

        def run() -> None:
            task = downloader.download(url)
            self.tasks.append(task)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return {"ok": True, "message": "下载任务已开始"}

    def get_tasks(self) -> list[dict]:
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
            for task in self.tasks
        ]

    def get_logs(self) -> dict:
        return {"lines": []}


def _tool_to_dict(status) -> dict:
    return {
        "name": status.name,
        "available": status.available,
        "version": status.version,
        "path": str(status.path) if status.path else "",
        "source": status.source,
        "message": status.message,
    }


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
