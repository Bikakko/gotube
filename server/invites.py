"""Invite code creation, validation and registration helpers."""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from fastapi import HTTPException
from sqlalchemy import or_, update
from sqlalchemy.orm import Session

from .db import InviteCode, User
from .user_profile import display_name_key, validate_display_name, validate_new_password

USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{3,32}$")


def generate_invite_code() -> str:
    """Generate invite code plaintext."""
    return secrets.token_urlsafe(16)


def hash_invite_code(code: str) -> str:
    """Hash invite code plaintext for storage."""
    return hashlib.sha256(code.strip().encode("utf-8")).hexdigest()


def create_invite(
    session: Session,
    admin: User,
    *,
    max_uses: int = 1,
    expires_hours: int | None = None,
    storage_quota_mb: int | None = None,
) -> dict[str, Any]:
    """Create an invite code and return the plaintext once."""
    if admin.role != "admin":
        raise HTTPException(status_code=403, detail="权限不足")
    if max_uses < 1 or max_uses > 100:
        raise HTTPException(status_code=422, detail="邀请码使用次数必须在 1 到 100 之间")
    if expires_hours is not None and (expires_hours < 1 or expires_hours > 24 * 365):
        raise HTTPException(status_code=422, detail="过期时间必须在 1 小时到 365 天之间")
    if storage_quota_mb is not None and storage_quota_mb < 0:
        raise HTTPException(status_code=422, detail="视频库空间不能为负数")

    code = generate_invite_code()
    now = datetime.now(UTC)
    invite = InviteCode(
        code_hash=hash_invite_code(code),
        code_plain=code,
        created_by_user_id=admin.id,
        max_uses=max_uses,
        used_count=0,
        expires_at=now + timedelta(hours=expires_hours) if expires_hours else None,
        is_active=True,
        created_at=now,
        storage_quota_mb=storage_quota_mb,
    )
    session.add(invite)
    session.flush()
    return _invite_to_dict(invite, include_code=code)


def list_invites(session: Session) -> list[dict[str, Any]]:
    """List invite codes with plaintext (for admin masked display)."""
    invites = session.query(InviteCode).order_by(InviteCode.created_at.desc()).all()
    return [_invite_to_dict(invite) for invite in invites]


def revoke_invite(session: Session, invite_id: int) -> dict[str, Any]:
    """Deactivate an invite code."""
    invite = session.query(InviteCode).filter(InviteCode.id == invite_id).first()
    if not invite:
        raise HTTPException(status_code=404, detail="邀请码不存在")
    invite.is_active = False
    session.flush()
    return _invite_to_dict(invite)


def consume_invite(session: Session, code: str) -> InviteCode:
    """Validate and consume one invite use."""
    code_hash = hash_invite_code(code)
    invite = session.query(InviteCode).filter(InviteCode.code_hash == code_hash).first()
    if not invite or not invite.is_active:
        raise HTTPException(status_code=400, detail="邀请码无效")
    if _is_expired(invite):
        raise HTTPException(status_code=400, detail="邀请码已过期")
    if invite.used_count >= invite.max_uses:
        raise HTTPException(status_code=400, detail="邀请码已用完")

    now = datetime.now(UTC)
    result = session.execute(
        update(InviteCode)
        .where(
            InviteCode.id == invite.id,
            InviteCode.is_active == True,
            or_(InviteCode.expires_at.is_(None), InviteCode.expires_at >= now),
            InviteCode.used_count < InviteCode.max_uses,
        )
        .values(used_count=InviteCode.used_count + 1)
    )
    if result.rowcount != 1:
        raise HTTPException(status_code=400, detail="邀请码已失效")

    session.flush()
    return session.query(InviteCode).filter(InviteCode.id == invite.id).one()


def register_user_with_invite(
    session: Session,
    username: str,
    display_name: str,
    password: str,
    invite_code: str,
) -> User:
    """Register a regular user with a valid invite code."""
    username = username.strip()
    invite_code = invite_code.strip()
    display_name = validate_display_name(display_name)
    password = validate_new_password(password)

    if not USERNAME_RE.fullmatch(username):
        raise HTTPException(status_code=422, detail="用户名需为 3-32 位字母、数字、下划线或短横线")
    if not invite_code:
        raise HTTPException(status_code=422, detail="邀请码不能为空")
    if session.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")

    invite = consume_invite(session, invite_code)

    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    user = User(
        username=username,
        display_name=display_name,
        display_name_key=display_name_key(display_name),
        password_hash=password_hash,
        role="user",
        is_active=True,
        storage_quota_mb=invite.storage_quota_mb,
    )
    session.add(user)
    session.flush()
    return user


def _is_expired(invite: InviteCode) -> bool:
    if invite.expires_at is None:
        return False
    expires_at = invite.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return datetime.now(UTC) > expires_at


def _invite_status(invite: InviteCode) -> str:
    if not invite.is_active:
        return "revoked"
    if _is_expired(invite):
        return "expired"
    if invite.used_count >= invite.max_uses:
        return "used_up"
    return "active"


def _invite_to_dict(invite: InviteCode, include_code: str | None = None) -> dict[str, Any]:
    data = {
        "id": invite.id,
        "max_uses": invite.max_uses,
        "used_count": invite.used_count,
        "expires_at": invite.expires_at.isoformat() if invite.expires_at else None,
        "is_active": invite.is_active,
        "created_at": invite.created_at.isoformat() if invite.created_at else None,
        "status": _invite_status(invite),
        "storage_quota_mb": invite.storage_quota_mb,
    }
    code = include_code or invite.code_plain
    if code:
        data["code"] = code
    return data
