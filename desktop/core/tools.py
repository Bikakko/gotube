"""Tool detection and update helpers for GoTube Desktop."""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ToolStatus:
    name: str
    available: bool
    version: str = ""
    path: Path | None = None
    source: str = ""
    message: str = ""


@dataclass(slots=True)
class ToolActionResult:
    ok: bool
    message: str
    stdout: str = ""
    stderr: str = ""


def detect_ffmpeg(*, configured_path: Path | None = None) -> ToolStatus:
    if configured_path is not None:
        path = Path(configured_path)
        if path.is_file():
            return ToolStatus(
                name="ffmpeg",
                available=True,
                path=path,
                source="configured",
                message="已配置 ffmpeg",
            )
        return ToolStatus(
            name="ffmpeg",
            available=False,
            path=path,
            source="configured",
            message=f"未找到 ffmpeg: {path}",
        )

    resolved = shutil.which("ffmpeg")
    if not resolved:
        return ToolStatus(name="ffmpeg", available=False, message="未检测到 ffmpeg")

    return ToolStatus(
        name="ffmpeg",
        available=True,
        path=Path(resolved),
        source="path",
        version=_command_first_line([resolved, "-version"]),
        message="已检测到 ffmpeg",
    )


def detect_ytdlp() -> ToolStatus:
    try:
        from yt_dlp.version import __version__
    except Exception as exc:
        return ToolStatus(name="yt-dlp", available=False, message=f"未检测到 yt-dlp: {exc}")

    return ToolStatus(
        name="yt-dlp",
        available=True,
        version=__version__,
        source="python-package",
        message="已检测到 yt-dlp",
    )


def upgrade_ytdlp(*, python_executable: str | None = None) -> ToolActionResult:
    executable = python_executable or sys.executable
    try:
        result = subprocess.run(
            [executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return ToolActionResult(ok=False, message=str(exc))

    if result.returncode != 0:
        return ToolActionResult(
            ok=False,
            message="yt-dlp 升级失败",
            stdout=result.stdout or "",
            stderr=result.stderr or "",
        )

    return ToolActionResult(
        ok=True,
        message="yt-dlp 已升级",
        stdout=result.stdout or "",
        stderr=result.stderr or "",
    )


def _command_first_line(args: list[str]) -> str:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    lines = (result.stdout or result.stderr or "").splitlines()
    return lines[0] if lines else ""
