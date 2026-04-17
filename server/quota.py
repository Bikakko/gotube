"""Per-user video library quota helpers."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from .config import settings
from .db import MediaAsset, User, UserVideoItem


def get_effective_quota_bytes(user: User) -> int | None:
    """Return the user's quota in bytes; admins are unlimited."""
    if user.role == "admin":
        return None
    quota_mb = user.storage_quota_mb
    if quota_mb is None:
        quota_mb = settings.user_storage_quota_mb
    if quota_mb <= 0:
        return None
    return quota_mb * 1024 * 1024


def refresh_user_storage_usage(session: Session, user_id: int) -> int:
    """Recalculate and persist active user library usage."""
    used = (
        session.query(func.coalesce(func.sum(MediaAsset.size_bytes), 0))
        .join(UserVideoItem, UserVideoItem.media_asset_id == MediaAsset.id)
        .filter(
            UserVideoItem.owner_user_id == user_id,
            UserVideoItem.deleted_at.is_(None),
        )
        .scalar()
    )
    used_int = int(used or 0)
    user = session.query(User).filter(User.id == user_id).first()
    if user:
        user.storage_used_bytes = used_int
        session.flush()
    return used_int


def user_can_add_media(session: Session, user: User, size_bytes: int) -> bool:
    """Check whether adding one media item would fit the user's library quota."""
    quota = get_effective_quota_bytes(user)
    if quota is None:
        return True
    current = refresh_user_storage_usage(session, user.id)
    return current + max(0, int(size_bytes or 0)) <= quota
