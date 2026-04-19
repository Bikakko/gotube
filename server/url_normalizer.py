"""Platform-aware media URL normalization for reuse lookup."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


TRACKING_QUERY_KEYS = {
    "t",
    "start",
    "time_continue",
    "progress",
    "seek",
    "spm_id_from",
    "vd_source",
    "share_source",
    "share_medium",
    "share_plat",
    "share_session_id",
    "timestamp",
    "share_times",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "si",
    "s",
}


@dataclass(frozen=True)
class NormalizedMediaUrl:
    original_url: str
    canonical_url: str
    platform: str
    media_key: str


def normalize_media_url(url: str) -> NormalizedMediaUrl:
    original_url = (url or "").strip()
    if not original_url:
        return NormalizedMediaUrl("", "", "", "")

    try:
        parsed = urlparse(original_url)
    except Exception:
        return NormalizedMediaUrl(original_url, original_url, "", f"url:{original_url}")

    host = (parsed.hostname or "").lower()
    if _is_youtube(host):
        return _normalize_youtube(original_url, parsed)
    if _is_bilibili(host):
        return _normalize_bilibili(original_url, parsed)
    if _is_twitter(host):
        return _normalize_twitter(original_url, parsed)
    return _normalize_unknown(original_url, parsed)


def _normalize_youtube(original_url: str, parsed) -> NormalizedMediaUrl:
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    video_id = query.get("v", "").strip()

    if not video_id and parsed.hostname and "youtu.be" in parsed.hostname.lower():
        video_id = parsed.path.strip("/").split("/", 1)[0]
    if not video_id:
        shorts = re.match(r"^/shorts/([^/?#]+)", parsed.path)
        if shorts:
            video_id = shorts.group(1)
    if not video_id:
        embed = re.match(r"^/embed/([^/?#]+)", parsed.path)
        if embed:
            video_id = embed.group(1)

    if video_id:
        canonical_url = f"https://www.youtube.com/watch?v={video_id}"
        return NormalizedMediaUrl(original_url, canonical_url, "youtube", f"youtube:{video_id}")

    canonical_url = _canonical_url(parsed, netloc="www.youtube.com")
    return NormalizedMediaUrl(original_url, canonical_url, "youtube", f"url:{canonical_url}")


def _normalize_bilibili(original_url: str, parsed) -> NormalizedMediaUrl:
    match = re.search(r"/video/([^/?#]+)", parsed.path)
    if match:
        video_id = match.group(1)
        query_pairs = _kept_query_pairs(parsed.query, keep_keys={"p"})
        query = urlencode(query_pairs)
        canonical_url = f"https://www.bilibili.com/video/{video_id}"
        if query:
            canonical_url = f"{canonical_url}?{query}"
        media_key = f"bilibili:{video_id}" + (f":{query}" if query else "")
        return NormalizedMediaUrl(original_url, canonical_url, "bilibili", media_key)

    canonical_url = _canonical_url(parsed, netloc="www.bilibili.com")
    return NormalizedMediaUrl(original_url, canonical_url, "bilibili", f"url:{canonical_url}")


def _normalize_twitter(original_url: str, parsed) -> NormalizedMediaUrl:
    match = re.search(r"/status(?:es)?/(\d+)", parsed.path)
    if not match:
        match = re.search(r"/i/web/status/(\d+)", parsed.path)
    if match:
        status_id = match.group(1)
        canonical_url = f"https://x.com/i/status/{status_id}"
        return NormalizedMediaUrl(original_url, canonical_url, "twitter", f"twitter:{status_id}")

    canonical_url = _canonical_url(parsed, netloc="x.com")
    return NormalizedMediaUrl(original_url, canonical_url, "twitter", f"url:{canonical_url}")


def _normalize_unknown(original_url: str, parsed) -> NormalizedMediaUrl:
    canonical_url = _canonical_url(parsed)
    platform = (parsed.hostname or "").lower()
    return NormalizedMediaUrl(original_url, canonical_url, platform, f"url:{canonical_url}")


def _canonical_url(parsed, *, netloc: str | None = None) -> str:
    query = urlencode(_kept_query_pairs(parsed.query))
    scheme = (parsed.scheme or "https").lower()
    host = (netloc or parsed.netloc).lower()
    path = parsed.path.rstrip("/") or parsed.path
    return urlunparse((scheme, host, path, "", query, ""))


def _kept_query_pairs(query: str, *, keep_keys: set[str] | None = None) -> list[tuple[str, str]]:
    pairs = []
    for key, value in parse_qsl(query, keep_blank_values=True):
        key_lower = key.lower()
        if keep_keys is not None:
            if key_lower not in keep_keys:
                continue
        elif key_lower in TRACKING_QUERY_KEYS:
            continue
        pairs.append((key, value))
    return sorted(pairs)


def _is_youtube(host: str) -> bool:
    return "youtube.com" in host or "youtu.be" in host


def _is_bilibili(host: str) -> bool:
    return "bilibili.com" in host or "b23.tv" in host


def _is_twitter(host: str) -> bool:
    return "twitter.com" in host or "x.com" in host
