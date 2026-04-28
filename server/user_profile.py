"""User profile validation and serialization helpers."""

from __future__ import annotations

import re
import unicodedata

from fastapi import HTTPException


DISPLAY_NAME_MIN_LENGTH = 2
DISPLAY_NAME_MAX_LENGTH = 32
PASSWORD_MIN_LENGTH = 6
PASSWORD_MAX_LENGTH = 64
FORBIDDEN_DISPLAY_NAME_CHARS = set('<>"\'`/\\')


def normalize_display_name(value: str) -> str:
    """Normalize display-name whitespace without changing visible letters."""
    value = str(value or "")
    if any(ch in "\r\n\t" for ch in value):
        raise HTTPException(status_code=422, detail="昵称不能包含换行或制表符")
    collapsed = re.sub(r" +", " ", value.replace("\u3000", " ").strip())
    return collapsed


def display_name_key(value: str) -> str:
    """Build a stable comparison/search key for a display name."""
    return normalize_display_name(value).casefold()


def validate_display_name(value: str) -> str:
    """Validate and normalize a safe multilingual display name."""
    normalized = normalize_display_name(value)
    length = len(normalized)
    if length < DISPLAY_NAME_MIN_LENGTH or length > DISPLAY_NAME_MAX_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"昵称长度需为 {DISPLAY_NAME_MIN_LENGTH} 到 {DISPLAY_NAME_MAX_LENGTH} 个字符",
        )

    for char in normalized:
        if char in FORBIDDEN_DISPLAY_NAME_CHARS:
            raise HTTPException(status_code=422, detail="昵称包含不允许使用的特殊字符")
        if unicodedata.category(char)[0] == "C":
            raise HTTPException(status_code=422, detail="昵称包含不允许使用的控制字符")
        if char == " " or char in "._-":
            continue
        category = unicodedata.category(char)[0]
        if category not in {"L", "N", "M"}:
            raise HTTPException(status_code=422, detail="昵称仅支持文字、数字、空格、点、短横线和下划线")

    return normalized


def validate_new_password(value: str) -> str:
    """Validate a user-supplied password and return the trimmed value."""
    normalized = str(value or "").strip()
    if len(normalized) < PASSWORD_MIN_LENGTH or len(normalized) > PASSWORD_MAX_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"新密码长度需为 {PASSWORD_MIN_LENGTH} 到 {PASSWORD_MAX_LENGTH} 位",
        )
    if not normalized:
        raise HTTPException(status_code=422, detail="新密码不能为空")
    return normalized


def get_display_name(user) -> str:
    """Return the effective display name for a user record."""
    return str(getattr(user, "display_name", "") or getattr(user, "username", ""))


def build_user_identity(user) -> dict:
    """Build the standard user-identity payload for frontend display."""
    return {
        "id": user.id,
        "username": user.username,
        "display_name": get_display_name(user),
        "role": user.role,
    }
