"""Runtime health checks for release readiness and admin diagnostics."""

from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import uuid
from pathlib import Path
from typing import Any

from .config import settings
from .cookie_store import diagnose_cookie_content, get_active_cookies_file_for_status

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
    elif cookies_path is None:
        active_cookies = None
    else:
        active_cookies = Path(cookies_path).resolve()

    cookie_info = _cookie_health(active_cookies)
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
        "git": _git_info(root),
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
        "yt_dlp_version": yt_dlp_version,
        "blockers": blockers,
    }


def _cookie_health(cookies_path: Path | None) -> dict[str, Any]:
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
        "source": "upload",
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


def _git_info(project_root: Path) -> dict[str, str]:
    return {
        "branch": _git_output(project_root, ["git", "rev-parse", "--abbrev-ref", "HEAD"]),
        "commit": _git_output(project_root, ["git", "rev-parse", "--short", "HEAD"]),
    }


def _git_output(project_root: Path, args: list[str]) -> str:
    try:
        result = subprocess.run(args, cwd=project_root, capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()
