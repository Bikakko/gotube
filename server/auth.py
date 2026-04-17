"""Shared authentication dependencies and token helpers."""

from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .db import AuthToken, User, get_session


async def get_db():
    """FastAPI dependency: provide a database session."""
    with get_session() as session:
        yield session


def cleanup_expired_tokens(db: Session) -> None:
    """Mark expired auth tokens as inactive."""
    now = datetime.now(UTC)
    expired_tokens = db.query(AuthToken).filter(
        AuthToken.expires_at < now,
        AuthToken.is_active == True,
    ).all()

    for auth_token in expired_tokens:
        auth_token.is_active = False

    if expired_tokens:
        db.commit()


def verify_token(db: Session, token: str | None) -> dict | None:
    """Validate a token and return a small auth payload."""
    if not token:
        return None

    auth_token = db.query(AuthToken).filter(
        AuthToken.token == token,
        AuthToken.is_active == True,
    ).first()
    if not auth_token:
        return None

    now = datetime.now(UTC)
    expires_at = auth_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    if now > expires_at:
        auth_token.is_active = False
        db.commit()
        return None

    user = db.query(User).filter(User.id == auth_token.user_id).first()
    if not user or not user.is_active:
        auth_token.is_active = False
        db.commit()
        return None

    auth_token.last_used_at = datetime.now(UTC)
    db.commit()

    return {
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
        "expiry": auth_token.expires_at.timestamp(),
    }


def get_bearer_token(request: Request) -> str | None:
    """Extract a Bearer token from an Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    return auth_header[7:].strip()


async def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Return the current authenticated active user."""
    token = get_bearer_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="未授权访问")

    cleanup_expired_tokens(db)
    payload = verify_token(db, token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")

    user = db.query(User).filter(User.id == payload["user_id"]).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")
    return user


async def get_optional_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User | None:
    """Return the current user when a valid Bearer token is present."""
    token = get_bearer_token(request)
    if not token:
        return None

    cleanup_expired_tokens(db)
    payload = verify_token(db, token)
    if not payload:
        return None

    user = db.query(User).filter(User.id == payload["user_id"]).first()
    if not user or not user.is_active:
        return None
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Require the current user to be an admin."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="权限不足")
    return user
