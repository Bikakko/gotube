from datetime import datetime, timezone
import logging

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text,
    UniqueConstraint, create_engine, inspect
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .user_profile import display_name_key, get_display_name

logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    display_name = Column(String(64), nullable=False, default="")
    display_name_key = Column(String(96), nullable=False, default="", index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="user")  # admin/user
    is_active = Column(Boolean, nullable=False, default=True)
    storage_quota_mb = Column(Integer, nullable=True)
    storage_used_bytes = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "display_name": get_display_name(self),
            "role": self.role,
            "is_active": self.is_active,
            "storage_quota_mb": self.storage_quota_mb,
            "storage_used_bytes": self.storage_used_bytes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }


class UserLog(Base):
    __tablename__ = "user_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(50), nullable=False)
    ip_address = Column(String(45), nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class AuthToken(Base):
    __tablename__ = "auth_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(128), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_used_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, nullable=False, default=True, index=True)


class SchemaMigration(Base):
    __tablename__ = "schema_migrations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(Integer, unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    applied_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fingerprint = Column(String(64), unique=True, nullable=False, index=True)
    file_hash = Column(String(32), nullable=False, index=True)
    filename = Column(Text, nullable=False)
    filepath = Column(Text, nullable=False)
    size_bytes = Column(Integer, nullable=False, default=0)
    title = Column(Text, nullable=False, default="")
    thumbnail = Column(Text, nullable=False, default="")
    duration = Column(Float, nullable=True)
    source_url = Column(Text, nullable=False, default="")
    meta_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_seen_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class MediaSource(Base):
    __tablename__ = "media_sources"
    __table_args__ = (
        UniqueConstraint("normalized_url", name="uq_media_source_normalized_url"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    media_asset_id = Column(Integer, ForeignKey("media_assets.id"), nullable=False, index=True)
    source_url = Column(Text, nullable=False, default="")
    normalized_url = Column(Text, nullable=False)
    platform = Column(String(50), nullable=False, default="")
    platform_video_id = Column(String(128), nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_seen_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class UserVideoItem(Base):
    __tablename__ = "user_video_items"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "media_asset_id", name="uq_user_video_item_owner_media"),
        UniqueConstraint("share_token", name="uq_user_video_item_share_token"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    media_asset_id = Column(Integer, ForeignKey("media_assets.id"), nullable=False, index=True)
    display_title = Column(Text, nullable=False, default="")
    share_token = Column(String(64), nullable=False, index=True)
    share_enabled = Column(Boolean, nullable=False, default=True)
    created_from = Column(String(32), nullable=False, default="download")
    saved_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    deleted_at = Column(DateTime, nullable=True, index=True)


class InviteCode(Base):
    __tablename__ = "invite_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code_hash = Column(String(128), unique=True, nullable=False, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    max_uses = Column(Integer, nullable=False, default=1)
    used_count = Column(Integer, nullable=False, default=0)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


# ── 数据库初始化 ──

_engine = None
_SessionLocal = None


def init_db(db_path: str) -> None:
    """初始化数据库引擎和会话工厂"""
    global _engine, _SessionLocal
    logger.info("初始化数据库: %s", db_path)
    _engine = create_engine(f"sqlite:///{db_path}", pool_pre_ping=True)
    _SessionLocal = sessionmaker(bind=_engine)
    Base.metadata.create_all(_engine)  # 自动建表（不存在的表才创建）
    from .config import settings
    from .migrations import run_v4_migrations

    run_v4_migrations(_engine, settings.get_download_dir())


def get_session() -> Session:
    """获取数据库会话"""
    if _SessionLocal is None:
        raise RuntimeError("数据库未初始化，请先调用 init_db()")
    return _SessionLocal()


def sync_admins_from_env(session: Session, admins_config: list[dict[str, str]]) -> None:
    """
    同步 .env 中的管理员账号到数据库。
    
    规则：
    1. .env 有但数据库没有 → 创建（role=admin）
    2. .env 和数据库都有 → 同步密码并设置 role=admin
    3. 数据库有但 .env 没有 → 降级为 user（仅限 role=admin 的记录）
    
    安全保证：
    - 只查询 role=admin 的记录
    - 只降级 role=admin 且不在配置中的记录
    - 绝不删除或修改 role != admin 的正常用户
    """
    import bcrypt

    # 1. 查询数据库中所有 role=admin 的记录
    db_admins = session.query(User).filter(User.role == "admin").all()
    db_admin_map = {u.username: u for u in db_admins}

    # 2. .env 中的用户名集合
    env_admin_names = {a["username"] for a in admins_config}

    created = 0
    updated = 0
    demoted = 0

    # 3. 处理 .env 中的每个账号
    for admin_conf in admins_config:
        username = admin_conf["username"]
        password = admin_conf["password"]

        if username not in db_admin_map:
            # 按用户名查找（可能 role 不是 admin）
            existing_user = session.query(User).filter(User.username == username).first()
            
            if existing_user is not None:
                # 用户存在但不是 admin，提升为 admin
                logger.info("[admin同步] 提升用户 %s 为管理员", username)
                existing_user.role = "admin"
                existing_user.is_active = True
                if not existing_user.display_name:
                    existing_user.display_name = username
                if not existing_user.display_name_key:
                    existing_user.display_name_key = display_name_key(existing_user.display_name)
                
                # 同步密码
                try:
                    password_match = bcrypt.checkpw(
                        password.encode('utf-8'),
                        existing_user.password_hash.encode('utf-8')
                    )
                    if not password_match:
                        salt = bcrypt.gensalt()
                        existing_user.password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
                        updated += 1
                except Exception as e:
                    logger.warning("[admin同步] 密码校验异常，强制更新: %s, 错误: %s", username, e)
                    salt = bcrypt.gensalt()
                    existing_user.password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
                    updated += 1
            else:
                # 创建新管理员
                logger.info("[admin同步] 创建管理员: %s", username)
                salt = bcrypt.gensalt()
                pwd_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

                new_admin = User(
                    username=username,
                    display_name=username,
                    display_name_key=display_name_key(username),
                    password_hash=pwd_hash,
                    role="admin",
                    is_active=True,
                )
                session.add(new_admin)
                created += 1
        else:
            # 同步密码（如果变了）
            db_admin = db_admin_map[username]
            db_admin.is_active = True
            if not db_admin.display_name:
                db_admin.display_name = username
            if not db_admin.display_name_key:
                db_admin.display_name_key = display_name_key(db_admin.display_name)
            try:
                password_match = bcrypt.checkpw(
                    password.encode('utf-8'),
                    db_admin.password_hash.encode('utf-8')
                )
                if not password_match:
                    logger.info("[admin同步] 更新管理员密码: %s", username)
                    salt = bcrypt.gensalt()
                    db_admin.password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
                    updated += 1
            except Exception as e:
                # 如果数据库哈希格式异常，强制更新
                logger.warning("[admin同步] 密码校验异常，强制更新: %s, 错误: %s", username, e)
                salt = bcrypt.gensalt()
                db_admin.password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
                updated += 1

    # 4. 降级数据库中不在 .env 配置中的 admin 账号（不删除，降级为 user）
    for username, db_admin in db_admin_map.items():
        if username not in env_admin_names:
            logger.warning("[admin同步] 降级非配置管理员 %s 为普通用户", username)
            db_admin.role = "user"
            demoted += 1

    session.commit()

    if created or updated or demoted:
        logger.info("[admin同步] 完成: 创建=%d, 更新=%d, 降级=%d", created, updated, demoted)
    else:
        logger.info("[admin同步] 管理员账号无变化")
