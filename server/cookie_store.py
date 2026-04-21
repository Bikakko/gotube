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
SOURCE_MARKER_FILENAME = ".cookies_runtime_source"

PLATFORM_COOKIE_REQUIREMENTS = {
    "bilibili": {"SESSDATA", "bili_jct", "DedeUserID"},
    "twitter": {"auth_token", "ct0"},
    "youtube": {"SAPISID", "__Secure-1PSID", "__Secure-3PSID"},
}

PLATFORM_DOMAIN_KEYWORDS = {
    "bilibili": ("bilibili.com", "b23.tv"),
    "twitter": ("x.com", "twitter.com"),
    "youtube": ("youtube.com", "google.com", "googlevideo.com", "youtu.be"),
}


def get_data_dir() -> Path:
    data_dir = settings.project_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_uploaded_cookies_path() -> Path:
    return get_data_dir() / COOKIE_FILENAME


def _get_import_marker_path() -> Path:
    return get_data_dir() / IMPORT_MARKER_FILENAME


def _get_source_marker_path() -> Path:
    return get_data_dir() / SOURCE_MARKER_FILENAME


def _mark_env_import_checked() -> None:
    marker = _get_import_marker_path()
    if not marker.exists():
        marker.write_text("1\n", encoding="utf-8")


def set_runtime_cookies_source(source: str) -> None:
    marker = _get_source_marker_path()
    marker.write_text(f"{source}\n", encoding="utf-8")


def clear_runtime_cookies_source() -> None:
    marker = _get_source_marker_path()
    if marker.exists():
        marker.unlink()


def get_runtime_cookies_source() -> str:
    marker = _get_source_marker_path()
    if not marker.exists():
        return "upload"
    try:
        source = marker.read_text(encoding="utf-8").strip()
    except OSError:
        return "upload"
    if source in {"upload", "env_import"}:
        return source
    return "upload"


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
    set_runtime_cookies_source("env_import")
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
        clear_runtime_cookies_source()
        return False
    uploaded_cookies.unlink()
    _mark_env_import_checked()
    clear_runtime_cookies_source()
    return True


def diagnose_cookie_content(content: str) -> dict[str, dict[str, object]]:
    """Report platform cookie-name coverage without exposing cookie values."""
    observed: dict[str, dict[str, set[str]]] = {
        platform: {"names": set(), "domains": set()}
        for platform in PLATFORM_COOKIE_REQUIREMENTS
    }

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        domain = parts[0].strip()
        name = parts[5].strip()
        if not domain or not name:
            continue
        normalized_domain = domain.lstrip(".").lower()
        for platform, keywords in PLATFORM_DOMAIN_KEYWORDS.items():
            if any(keyword in normalized_domain for keyword in keywords):
                observed[platform]["names"].add(name)
                observed[platform]["domains"].add(domain)

    diagnostics: dict[str, dict[str, object]] = {}
    for platform, required in PLATFORM_COOKIE_REQUIREMENTS.items():
        present = observed[platform]["names"] & required
        missing = required - present
        diagnostics[platform] = {
            "has_required": not missing,
            "present": sorted(present),
            "missing": sorted(missing),
            "domains": sorted(observed[platform]["domains"]),
        }
    return diagnostics
