"""
Pydantic 请求/响应模型

集中管理所有 API 的数据模型。
"""

from pydantic import BaseModel, Field, field_validator


class AddTaskRequest(BaseModel):
    """添加下载任务请求"""

    url: str
    session_id: str | None = None  # 匿名用户会话标识


class TaskResponse(BaseModel):
    """任务响应"""

    task_id: str
    url: str
    status: str
    progress: float
    speed: float
    eta: int
    filename: str
    error: str
    title: str
    thumbnail: str
    duration: float
    video_id: str = ""
    file_hash: str = ""
    is_duplicate: bool = False
    user_video_item_id: int | None = None
    media_asset_id: int | None = None
    share_token: str = ""
    created_at: str
    completed_at: str | None = None


class DeleteDownloadResponse(BaseModel):
    """删除下载响应"""

    status: str
    deleted_files: list[str]


# ── 用户管理模型 ──


class LoginRequest(BaseModel):
    """登录请求"""

    username: str = Field(alias="user")
    password: str = Field(alias="pass")


class UserResponse(BaseModel):
    """用户信息响应"""

    id: int
    username: str
    role: str
    is_active: bool
    created_at: str
    last_login: str | None


class CreateUserRequest(BaseModel):
    """创建用户请求"""

    username: str
    password: str
    role: str = "user"  # admin/user

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        if value not in {"admin", "user"}:
            raise ValueError("角色只能是 admin 或 user")
        return value


class UpdateUserRequest(BaseModel):
    """更新用户信息请求"""

    username: str | None = None
    role: str | None = None
    is_active: bool | None = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str | None) -> str | None:
        if value is not None and value not in {"admin", "user"}:
            raise ValueError("角色只能是 admin 或 user")
        return value


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""

    old_password: str | None = None  # 本人修改时需要验证旧密码
    new_password: str
