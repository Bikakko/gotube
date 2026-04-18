"""Runtime cookie file management.

Uploaded cookies in data/cookies.txt are the single runtime source. The legacy
.env cookie path is imported once for compatibility, then ignored until the
operator explicitly uploads cookies again.
"""

import shutil
from pathlib import Path

from .config import settings


COOKIE_FILENAME = "cookies.txt"
IMPORT_MARKER_FILENAME = ".cookies_env_imported"


def get_data_dir() -> Path:
    data_dir = settings.project_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_uploaded_cookies_path() -> Path:
    return get_data_dir() / COOKIE_FILENAME


def _get_import_marker_path() -> Path:
    return get_data_dir() / IMPORT_MARKER_FILENAME


def _mark_env_import_checked() -> None:
    marker = _get_import_marker_path()
    if not marker.exists():
        marker.write_text("1\n", encoding="utf-8")


def get_runtime_cookies_file() -> Path | None:
    """Return the cookie file actually used by yt-dlp."""
    uploaded_cookies = get_uploaded_cookies_path()
    if uploaded_cookies.exists():
        _mark_env_import_checked()
        return uploaded_cookies

    marker = _get_import_marker_path()
    if marker.exists():
        return None

    env_cookies = settings.get_cookies_file()
    if not env_cookies:
        _mark_env_import_checked()
        return None

    shutil.copy2(env_cookies, uploaded_cookies)
    _mark_env_import_checked()
    return uploaded_cookies


def get_existing_uploaded_cookies_file() -> Path | None:
    uploaded_cookies = get_uploaded_cookies_path()
    return uploaded_cookies if uploaded_cookies.exists() else None


def get_active_cookies_file_for_status() -> Path | None:
    """Return the current uploaded runtime cookie without importing legacy env."""
    return get_existing_uploaded_cookies_file()


def delete_uploaded_cookies_file() -> bool:
    uploaded_cookies = get_uploaded_cookies_path()
    if not uploaded_cookies.exists():
        _mark_env_import_checked()
        return False
    uploaded_cookies.unlink()
    _mark_env_import_checked()
    return True
