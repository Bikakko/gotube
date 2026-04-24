"""Local configuration for GoTube Desktop."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class DesktopConfig:
    download_dir: Path
    cookies_file: Path | None = None
    ffmpeg_path: Path | None = None
    browser_cookie_source: str | None = None
    ytdlp_update_policy: str = "manual"
    last_window_size: tuple[int, int] | None = None


class DesktopConfigStore:
    def __init__(
        self,
        *,
        appdata_dir: Path | None = None,
        user_profile: Path | None = None,
    ) -> None:
        self.appdata_dir = Path(appdata_dir or os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        self.user_profile = Path(user_profile or os.environ.get("USERPROFILE") or Path.home())
        self.config_dir = self.appdata_dir / "GoTubeDesktop"
        self.config_path = self.config_dir / "config.json"

    def load(self) -> DesktopConfig:
        if not self.config_path.exists():
            return self.default_config()

        try:
            raw = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self.default_config()

        return DesktopConfig(
            download_dir=self._path_or_default(raw.get("download_dir"), self.default_download_dir),
            cookies_file=self._optional_path(raw.get("cookies_file")),
            ffmpeg_path=self._optional_path(raw.get("ffmpeg_path")),
            browser_cookie_source=self._optional_str(raw.get("browser_cookie_source")),
            ytdlp_update_policy=self._optional_str(raw.get("ytdlp_update_policy")) or "manual",
            last_window_size=self._window_size(raw.get("last_window_size")),
        )

    def save(self, config: DesktopConfig) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        data = asdict(config)
        for key in ("download_dir", "cookies_file", "ffmpeg_path"):
            value = data.get(key)
            data[key] = str(value) if value else None
        self.config_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def default_config(self) -> DesktopConfig:
        return DesktopConfig(download_dir=self.default_download_dir)

    @property
    def default_download_dir(self) -> Path:
        return self.user_profile / "Downloads" / "GoTube"

    @staticmethod
    def _optional_str(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        value = value.strip()
        return value or None

    def _optional_path(self, value: Any) -> Path | None:
        text = self._optional_str(value)
        return Path(text) if text else None

    def _path_or_default(self, value: Any, default: Path) -> Path:
        text = self._optional_str(value)
        return Path(text) if text else default

    @staticmethod
    def _window_size(value: Any) -> tuple[int, int] | None:
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            return None
        width, height = value
        if not isinstance(width, int) or not isinstance(height, int):
            return None
        if width <= 0 or height <= 0:
            return None
        return width, height
