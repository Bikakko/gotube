"""Single-user downloader core for GoTube Desktop."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from .tasks import DesktopTask


ProgressCallback = Callable[[DesktopTask], None]


class DesktopDownloader:
    def __init__(
        self,
        *,
        download_dir: Path,
        cookies_file: Path | None = None,
        browser_cookie_source: str | None = None,
        ffmpeg_path: Path | None = None,
    ) -> None:
        self.download_dir = Path(download_dir)
        self.cookies_file = Path(cookies_file) if cookies_file else None
        self.browser_cookie_source = browser_cookie_source.strip().lower() if browser_cookie_source else None
        self.ffmpeg_path = Path(ffmpeg_path) if ffmpeg_path else None

    def build_ytdlp_options(self, *, task: DesktopTask | None = None) -> dict:
        outtmpl = str(self.download_dir / "%(title).200B_%(id)s.%(ext)s")
        options = {
            "outtmpl": outtmpl,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
        }
        if self.cookies_file:
            options["cookiefile"] = str(self.cookies_file)
        elif self.browser_cookie_source:
            options["cookiesfrombrowser"] = (self.browser_cookie_source,)
        if self.ffmpeg_path:
            is_executable_path = self.ffmpeg_path.name.lower() in {"ffmpeg", "ffmpeg.exe"}
            options["ffmpeg_location"] = str(self.ffmpeg_path.parent if is_executable_path else self.ffmpeg_path)
        if task is not None:
            options["progress_hooks"] = [self._progress_hook(task)]
        return options

    def download(self, url: str, *, on_progress: ProgressCallback | None = None) -> DesktopTask:
        task = DesktopTask.create(url=url)
        task.mark_running()
        if on_progress:
            on_progress(task)

        try:
            from yt_dlp import YoutubeDL

            self.download_dir.mkdir(parents=True, exist_ok=True)
            with YoutubeDL(self.build_ytdlp_options(task=task)) as ydl:
                info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            task.mark_completed(file_path=filename)
            if on_progress:
                on_progress(task)
            return task
        except Exception as exc:
            task.mark_failed(str(exc))
            if on_progress:
                on_progress(task)
            return task

    def _progress_hook(self, task: DesktopTask) -> Callable[[dict], None]:
        def hook(data: dict) -> None:
            status = data.get("status")
            if status == "downloading":
                total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
                downloaded = data.get("downloaded_bytes") or 0
                percent = (downloaded / total * 100) if total else task.percent
                task.update_progress(
                    percent=percent,
                    speed=str(data.get("_speed_str") or ""),
                    eta=str(data.get("_eta_str") or ""),
                )
            elif status == "finished":
                task.update_progress(percent=100.0)

        return hook
