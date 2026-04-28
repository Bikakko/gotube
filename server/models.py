"""
Pydantic request/response models.

Centralize API payload schemas here.
"""

from pydantic import BaseModel, Field, field_validator


class AddTaskRequest(BaseModel):
    """Add-download-task request."""

    url: str
    session_id: str | None = None


class TaskResponse(BaseModel):
    """Download-task response."""

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
    """Delete-download response."""

    status: str
    deleted_files: list[str]


class LoginRequest(BaseModel):
    """Login request."""

    username: str = Field(alias="user")
    password: str = Field(alias="pass")


class UserIdentityResponse(BaseModel):
    """Compact user-identity payload for frontend display."""

    id: int
    username: str
    display_name: str
    role: str


class UserResponse(BaseModel):
    """User response for admin management."""

    id: int
    username: str
    display_name: str
    role: str
    is_active: bool
    storage_quota_mb: int | None = None
    storage_used_bytes: int = 0
    video_count: int = 0
    is_system_account: bool = False
    created_at: str
    last_login: str | None


class CreateUserRequest(BaseModel):
    """Admin create-user request."""

    username: str
    display_name: str
    password: str
    role: str = "user"

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        if value not in {"admin", "user"}:
            raise ValueError("角色只能是 admin 或 user")
        return value


class UpdateUserRequest(BaseModel):
    """Admin update-user request."""

    username: str | None = None
    display_name: str | None = None
    role: str | None = None
    is_active: bool | None = None
    storage_quota_mb: int | None = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str | None) -> str | None:
        if value is not None and value not in {"admin", "user"}:
            raise ValueError("角色只能是 admin 或 user")
        return value

    @field_validator("storage_quota_mb")
    @classmethod
    def validate_storage_quota_mb(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("视频库容量不能为负数")
        return value


class UpdateProfileRequest(BaseModel):
    """Current-user profile update request."""

    display_name: str


class ChangePasswordRequest(BaseModel):
    """Change-password request."""

    old_password: str | None = None
    new_password: str


class RegisterRequest(BaseModel):
    """Invite-based registration request."""

    username: str
    display_name: str
    password: str
    invite_code: str


class UpdateShareRequest(BaseModel):
    """Update share status request."""

    share_enabled: bool


class CreateInviteRequest(BaseModel):
    """Admin create-invite request."""

    max_uses: int = 1
    expires_hours: int | None = None


class InviteResponse(BaseModel):
    """Invite metadata response."""

    id: int
    max_uses: int
    used_count: int
    expires_at: str | None
    is_active: bool
    created_at: str | None
    status: str
    code: str | None = None
