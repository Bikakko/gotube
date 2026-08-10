"""Shared authentication dependencies and token helpers."""

from datetime import UTC, datetime, timedelta
import time

from fastapi import Depends, HTTPException, Request
from sqlalchemy import update
from sqlalchemy.orm import Session

from .db import AuthToken, User, get_session
from .user_profile import build_user_identity

_TOKEN_CLEANUP_INTERVAL_SECONDS = 60.0
_last_expired_token_cleanup_at = 0.0

SESSION_COOKIE_NAME = "gotube_session"
# 滑动过期：7 天内无任何活动则登录失效
SESSION_TTL_SECONDS = 7 * 24 * 3600
# 剩余有效期低于一半时才续期，避免每个请求都写库
_REFRESH_THRESHOLD_SECONDS = SESSION_TTL_SECONDS // 2


async def get_db():
    """FastAPI dependency: provide a database session."""
    with get_session() as session:
        yield session


def cleanup_expired_tokens(db: Session) -> None:
    """Mark expired auth tokens as inactive."""
    global _last_expired_token_cleanup_at
    now_monotonic = time.monotonic()
    if now_monotonic - _last_expired_token_cleanup_at < _TOKEN_CLEANUP_INTERVAL_SECONDS:
        return

    now = datetime.now(UTC)
    result = db.execute(
        update(AuthToken)
        .where(
            AuthToken.expires_at < now,
            AuthToken.is_active == True,
        )
        .values(is_active=False)
    )

    if result.rowcount:
        db.commit()
    _last_expired_token_cleanup_at = now_monotonic


def verify_token(db: Session, token: str | None) -> dict | None:
    """Validate a token and return a small auth payload."""
    if not token:
        return None

    row = (
        db.query(AuthToken, User)
        .join(User, User.id == AuthToken.user_id)
        .filter(
            AuthToken.token == token,
            AuthToken.is_active == True,
        )
        .first()
    )
    if not row:
        return None
    auth_token, user = row

    now = datetime.now(UTC)
    expires_at = auth_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    if now > expires_at:
        auth_token.is_active = False
        db.commit()
        return None

    if not user.is_active:
        auth_token.is_active = False
        db.commit()
        return None

    remaining = (expires_at - now).total_seconds()
    session_refreshed = remaining < _REFRESH_THRESHOLD_SECONDS
    if session_refreshed:
        # 滑动续期：有活动就延长有效期，中间件会同步刷新 Cookie 过期时间
        auth_token.expires_at = now + timedelta(seconds=SESSION_TTL_SECONDS)
    auth_token.last_used_at = now
    db.commit()

    return {
        **build_user_identity(user),
        "user_id": user.id,
        "expiry": auth_token.expires_at.timestamp(),
        "_session_refreshed": session_refreshed,
        "_user": user,
    }


def get_session_token(request: Request) -> str | None:
    """Extract the session token from the login cookie."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    return token.strip() or None


def set_session_cookie(response, token: str) -> None:
    """在响应上下发登录 Cookie（HttpOnly + SameSite=Lax）。"""
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_TTL_SECONDS,
        path="/",
        httponly=True,
        samesite="lax",
        secure=False,
    )


def clear_session_cookie(response) -> None:
    """清除登录 Cookie。"""
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")


def _mark_session_refreshed(request: Request, payload: dict) -> None:
    """标记本次请求触发了滑动续期，由中间件据此刷新 Cookie 过期时间。"""
    if payload.get("_session_refreshed"):
        request.state.session_cookie_refreshed = True


async def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Return the current authenticated active user."""
    token = get_session_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="未授权访问")

    cleanup_expired_tokens(db)
    payload = verify_token(db, token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")
    _mark_session_refreshed(request, payload)

    user = payload.get("_user") or db.query(User).filter(User.id == payload["user_id"]).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")
    return user


async def get_optional_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User | None:
    """Return the current user when a valid session cookie is present."""
    token = get_session_token(request)
    if not token:
        return None

    cleanup_expired_tokens(db)
    payload = verify_token(db, token)
    if not payload:
        return None
    _mark_session_refreshed(request, payload)

    user = payload.get("_user") or db.query(User).filter(User.id == payload["user_id"]).first()
    if not user or not user.is_active:
        return None
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Require the current user to be an admin."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="权限不足")
    return user
