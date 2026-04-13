from datetime import datetime, timezone
import logging

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Text,
    create_engine, inspect
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="user")  # admin/user/readonly
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "is_active": self.is_active,
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


def get_session() -> Session:
    """获取数据库会话"""
    if _SessionLocal is None:
        raise RuntimeError("数据库未初始化，请先调用 init_db()")
    return _SessionLocal()


def ensure_default_admin(session: Session, username: str, password: str) -> None:
    """确保存在默认管理员账户（首次启动时调用）"""
    import bcrypt
    admin = session.query(User).filter(User.role == "admin").first()
    if admin is None:
        logger.info("创建默认管理员账户: %s", username)
        # 生成盐并哈希密码
        salt = bcrypt.gensalt()
        pwd_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
        
        admin = User(
            username=username,
            password_hash=pwd_hash,
            role="admin",
            is_active=True,
        )
        session.add(admin)
        session.commit()
