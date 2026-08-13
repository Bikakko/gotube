"""Security validation helpers for public request parameters."""

import ipaddress
import re
import socket
from urllib.parse import urlparse

from fastapi import HTTPException

GUEST_SESSION_RE = re.compile(r"^guest_[a-z0-9]+_[a-z0-9]{4,32}$")
# 兼容旧版 8 位 CRC32 指纹，同时接受新版 32 位 SHA-256 指纹（128-bit）
HASH_ID_RE = re.compile(r"^[0-9a-f]{8,64}$")

_RESERVED_HOSTNAME_SUFFIXES = (
    ".local",
    ".internal",
    ".localhost",
    ".home.arpa",
    ".lan",
    ".localdomain",
)


def validate_guest_session_id(session_id: str | None) -> str:
    """Validate a browser-generated guest session id."""
    value = (session_id or "").strip()
    if not GUEST_SESSION_RE.fullmatch(value):
        raise HTTPException(status_code=400, detail="非法 session_id")
    return value


def validate_hash_id(hash_id: str | None) -> str:
    """Validate a public video hash id."""
    value = (hash_id or "").strip().lower()
    if not HASH_ID_RE.fullmatch(value):
        raise HTTPException(status_code=400, detail="非法视频标识")
    return value


def is_public_ip_address(ip_text: str) -> bool:
    """Return True when ip_text is a globally routable address.

    Uses ipaddress.is_global, which also excludes CGNAT/Tailscale
    (100.64.0.0/10), benchmark (198.18.0.0/15) and documentation ranges.
    """
    try:
        ip = ipaddress.ip_address(ip_text)
    except ValueError:
        return False
    # Map IPv4-mapped IPv6 (e.g. ::ffff:127.0.0.1) back to IPv4 before checking.
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global


def is_public_hostname(hostname: str) -> bool:
    """Return True unless the hostname is a local/private destination.

    Conservative SSRF guard: rejects literal non-public IPs, localhost,
    mDNS/internal reserved suffixes, and hostnames that resolve to any
    non-public address. Hostnames that fail to resolve are allowed through
    (yt-dlp will fail on its own), keeping legitimate downloads unaffected.
    """
    host = (hostname or "").strip().lower()
    if not host:
        return False
    if host == "localhost" or host.endswith(_RESERVED_HOSTNAME_SUFFIXES):
        return False

    if is_public_ip_address(host):
        return True
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass  # not an IP literal; resolve as a hostname below
    else:
        return False  # literal IP that is not public

    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except OSError:
        return True

    addresses = {info[4][0] for info in infos if info and len(info) > 4 and info[4]}
    if not addresses:
        return True
    return all(is_public_ip_address(address) for address in addresses)


def validate_public_http_url(url: str) -> None:
    """Reject non-http(s) URLs and URLs targeting local/private hosts (SSRF guard)."""
    try:
        parsed = urlparse(url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="URL 格式无效") from exc

    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="URL 必须使用 http:// 或 https:// 协议")

    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(status_code=400, detail="URL 缺少主机名")

    if not is_public_hostname(hostname):
        raise HTTPException(status_code=400, detail="不允许访问内网或本地地址")
