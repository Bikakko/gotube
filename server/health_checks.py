"""Runtime health checks for release readiness and admin diagnostics."""

from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import uuid
from collections import deque
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

from .config import settings
from .cookie_store import (
    diagnose_cookie_content,
    get_active_cookies_file_for_status,
    get_runtime_cookies_source,
)

_DEFAULT = object()


def collect_runtime_health(
    *,
    project_root: Path | None = None,
    download_dir: Path | None = None,
    db_path: Path | None = None,
    cookies_path: Path | None | object = _DEFAULT,
) -> dict[str, Any]:
    """Collect non-sensitive runtime diagnostics for admins."""
    root = Path(project_root or settings.project_root).resolve()
    resolved_download_dir = Path(download_dir or settings.get_download_dir()).resolve()
    resolved_db_path = Path(db_path or settings.db_file).resolve()
    if cookies_path is _DEFAULT:
        active_cookies = get_active_cookies_file_for_status()
        cookie_source = get_runtime_cookies_source() if active_cookies else "none"
    elif cookies_path is None:
        active_cookies = None
        cookie_source = "none"
    else:
        active_cookies = Path(cookies_path).resolve()
        cookie_source = "upload"

    cookie_info = _cookie_health(active_cookies, source=cookie_source)
    download_writable = _path_writable(resolved_download_dir, create_dir=True)
    database_writable = _sqlite_database_writable(resolved_db_path)
    ffmpeg_info = _command_version("ffmpeg", ["ffmpeg", "-version"])
    yt_dlp_version = _yt_dlp_version()

    blockers: list[str] = []
    if not download_writable:
        blockers.append("download_dir_not_writable")
    if not database_writable:
        blockers.append("database_not_writable")
    if not ffmpeg_info["available"]:
        blockers.append("ffmpeg_missing")
    if not yt_dlp_version:
        blockers.append("yt_dlp_missing")

    return {
        "project_root": str(root),
        "version": _app_version(root),
        "cookie_source": cookie_info["source"],
        "cookie_file_exists": cookie_info["exists"],
        "cookie_file_path": cookie_info["path"],
        "cookie_diagnostics": cookie_info["diagnostics"],
        "download_dir": str(resolved_download_dir),
        "download_dir_writable": download_writable,
        "database_path": str(resolved_db_path),
        "database_writable": database_writable,
        "ffmpeg_available": ffmpeg_info["available"],
        "ffmpeg_version": ffmpeg_info["version"],
        "ffmpeg_summary": _summarize_command_version(ffmpeg_info["version"], available=ffmpeg_info["available"]),
        "yt_dlp_version": yt_dlp_version,
        "yt_dlp_summary": yt_dlp_version or "未安装",
        "blockers": blockers,
    }


def read_runtime_logs(
    *,
    project_root: Path | None = None,
    log_path: Path | None = None,
    log_type: str = "app",
    line_limit: int = 120,
) -> dict[str, Any]:
    root = Path(project_root or settings.project_root).resolve()
    resolved_log_path = Path(log_path or _resolve_runtime_log_path(root)).resolve()
    limit = max(1, min(int(line_limit), 300))
    exists = resolved_log_path.exists()
    if not exists:
        return {
            "type": log_type,
            "path": str(resolved_log_path),
            "exists": False,
            "lines": [],
        }

    try:
        lines = deque(maxlen=limit)
        with resolved_log_path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                lines.append(line.rstrip("\r\n"))
    except OSError:
        return {
            "type": log_type,
            "path": str(resolved_log_path),
            "exists": True,
            "lines": [],
        }

    if log_type == "access":
        filtered = [line for line in lines if _is_access_log_line(line)]
    else:
        filtered = [line for line in lines if not _is_access_log_line(line)]

    return {
        "type": log_type,
        "path": str(resolved_log_path),
        "exists": True,
        "lines": filtered[-limit:],
    }


def _cookie_health(cookies_path: Path | None, *, source: str = "upload") -> dict[str, Any]:
    if not cookies_path or not cookies_path.exists():
        return {
            "source": "none",
            "exists": False,
            "path": "",
            "diagnostics": diagnose_cookie_content(""),
        }

    try:
        content = cookies_path.read_text(encoding="utf-8")
    except OSError:
        content = ""
    return {
        "source": source,
        "exists": True,
        "path": str(cookies_path),
        "diagnostics": diagnose_cookie_content(content),
    }


def _path_writable(path: Path, *, create_dir: bool = False) -> bool:
    try:
        if create_dir:
            path.mkdir(parents=True, exist_ok=True)
        if not path.is_dir():
            return False
        probe = path / f".gotube-health-{uuid.uuid4().hex}.tmp"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def _sqlite_database_writable(db_path: Path) -> bool:
    try:
        parent = db_path.parent
        parent.mkdir(parents=True, exist_ok=True)
        if not os.access(parent, os.W_OK):
            return False
        if db_path.exists() and not os.access(db_path, os.W_OK):
            return False
        conn = sqlite3.connect(str(db_path), timeout=2)
        try:
            conn.execute("SELECT 1").fetchone()
        finally:
            conn.close()
        return True
    except sqlite3.Error:
        return False
    except OSError:
        return False


def _command_version(command: str, args: list[str]) -> dict[str, Any]:
    if not shutil.which(command):
        return {"available": False, "version": ""}
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        return {"available": True, "version": ""}
    first_line = (result.stdout or result.stderr or "").splitlines()
    return {
        "available": True,
        "version": first_line[0] if first_line else "",
    }


def _yt_dlp_version() -> str:
    try:
        from yt_dlp.version import __version__
    except Exception:
        return ""
    return __version__

def _app_version(project_root: Path) -> str:
    version_file = project_root / "VERSION"
    try:
        return version_file.read_text(encoding="utf-8").strip() or "--"
    except OSError:
        return "--"


def _summarize_command_version(version: str, *, available: bool) -> str:
    if not available:
        return "未安装"
    if not version:
        return "已安装"
    parts = version.strip().split()
    if len(parts) >= 3:
        return parts[2]
    if len(parts) >= 2:
        return parts[1]
    return "已安装"


def _resolve_runtime_log_path(project_root: Path) -> Path:
    env_file = project_root / ".env"
    if env_file.exists():
        raw = dotenv_values(str(env_file))
        configured = (raw.get("GOTUBE_LOG_FILE") or "").strip()
        if configured:
            path = Path(configured)
            return path if path.is_absolute() else (project_root / path)
    return project_root / "server.log"


def _is_access_log_line(line: str) -> bool:
    return line.startswith('time="[') and ' method="' in line and ' status=' in line
