"""Security validation helpers for public request parameters."""

import re

from fastapi import HTTPException

GUEST_SESSION_RE = re.compile(r"^guest_[a-z0-9]+_[a-z0-9]{4,32}$")
HASH_ID_RE = re.compile(r"^[0-9a-f]{8}$")


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
