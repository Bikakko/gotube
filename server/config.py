"""
GoTube 配置管理

只从程序目录下的 .env 文件加载配置。
如果 .env 不存在或配置有误，程序会报错退出并输出详细日志。
不读取系统环境变量，确保多实例互不干扰。
"""

import sys
import re
from pathlib import Path

from dotenv import dotenv_values


# ── 加载 .env 文件 ──

_ENV_FILE = Path(__file__).parent.parent / ".env"

if not _ENV_FILE.exists():
    print(f"[配置错误] 配置文件不存在: {_ENV_FILE}", file=sys.stderr)
    print(f"  请创建 .env 文件，可参考 .env.example 中的模板。", file=sys.stderr)
    sys.exit(1)

_raw = dotenv_values(str(_ENV_FILE))
_errors: list[str] = []


def _s(key: str, required: bool = False, default: str = "") -> str:
    """读取字符串配置"""
    val = _raw.get(key)
    if val is None:
        if required:
            _errors.append(f"  {key} = (缺失，必填)")
            return default
        return default
    return val.strip()


def _i(key: str, required: bool = False, default: int | None = None,
       min_val: int | None = None, max_val: int | None = None) -> int:
    """读取整数配置"""
    val = _raw.get(key)
    if val is None:
        if required:
            _errors.append(f"  {key} = (缺失，必填)")
        return default or 0
    try:
        n = int(val.strip())
    except ValueError:
        _errors.append(f"  {key} = '{val}' (无效的数字)")
        return default or 0
    if min_val is not None and n < min_val:
        _errors.append(f"  {key} = {n} (值过小，最小 {min_val})")
    if max_val is not None and n > max_val:
        _errors.append(f"  {key} = {n} (值过大，最大 {max_val})")
    return n


def _b(key: str, default: bool) -> bool:
    """读取布尔配置"""
    val = _raw.get(key)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


_HIDDEN_PATH_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def validate_hidden_path(value: str) -> str:
    """Validate the configured hidden-path segment."""
    candidate = value or ""
    if not _HIDDEN_PATH_PATTERN.fullmatch(candidate):
        raise ValueError("hidden_path 仅允许 1-64 位字母、数字、下划线或短横线")
    return candidate


def _split_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part and part.strip()]


def validate_cors_origin(value: str) -> str:
    candidate = value.strip()
    if not (candidate.startswith("http://") or candidate.startswith("https://")):
        raise ValueError("CORS 来源必须以 http:// 或 https:// 开头")
    if "*" in candidate:
        raise ValueError("CORS 来源不允许使用通配符")
    return candidate.rstrip("/")


# ── 读取所有配置项 ──

_project_root: Path = Path(__file__).parent.parent

_port: int = _i("GOTUBE_PORT", required=True, min_val=1, max_val=65535)
_hidden_path_raw: str = _s("GOTUBE_HIDDEN_PATH", required=True)
try:
    _hidden_path: str = validate_hidden_path(_hidden_path_raw)
except ValueError as exc:
    _errors.append(f"  GOTUBE_HIDDEN_PATH = '{_hidden_path_raw}' ({exc})")
    _hidden_path = _hidden_path_raw
_max_concurrent: int = _i("GOTUBE_MAX_CONCURRENT", required=True, min_val=1, max_val=20)
_max_downloads_per_user: int = _i("GOTUBE_MAX_DOWNLOADS_PER_USER", required=False, default=1, min_val=0)
_download_dir: str = _s("GOTUBE_DOWNLOAD_DIR", required=True)
_www_dir: str = _s("GOTUBE_WWW_DIR", default="www")
_cookies_file: str = _s("GOTUBE_COOKIES_FILE")
_warp_proxy: str = _s("GOTUBE_WARP_PROXY")
_db_file: str = _s("GOTUBE_DB_FILE", default="./gotube.db")
_backup_dir: str = _s("GOTUBE_BACKUP_DIR", default="databackups")
_backup_interval_hours: int = _i("GOTUBE_BACKUP_INTERVAL_HOURS", default=24, min_val=1)
_backup_retention: int = _i("GOTUBE_BACKUP_RETENTION", default=3, min_val=1)

# 解析管理员账号列表（格式：用户名1:密码1,用户名2:密码2）
_raw_admins: str = _s("GOTUBE_ADMINS", required=True)
_admins: list[dict[str, str]] = []

# 常见弱密码黑名单（小写比对）
_WEAK_PASSWORDS = {
    "admin", "admin123", "admin888", "administrator", "root", "password",
    "password123", "passw0rd", "changeme", "qwerty", "abc123", "a123456",
    "123456", "12345678", "123456789", "1234567890", "111111", "000000",
    "666666", "888888", "123123", "112233", "iloveyou", "letmein",
}


def _validate_admin_password(username: str, password: str) -> str | None:
    """校验管理员密码强度，返回错误描述；通过返回 None。"""
    if len(password) < 8:
        return "密码长度至少 8 位"
    if password.lower() in _WEAK_PASSWORDS:
        return "密码过于常见，请更换"
    if password.lower() == username.lower():
        return "密码不能与用户名相同"
    return None


if _raw_admins:
    for pair in _raw_admins.split(","):
        pair = pair.strip()
        if not pair:
            continue
        parts = pair.split(":", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            _errors.append(f"  GOTUBE_ADMINS = '{pair}' (格式错误，应为 用户名:密码)")
        else:
            pwd_error = _validate_admin_password(parts[0], parts[1])
            if pwd_error:
                _errors.append(f"  GOTUBE_ADMINS = '{parts[0]}' ({pwd_error})")
            else:
                _admins.append({"username": parts[0], "password": parts[1]})

if not _admins:
    _errors.append("  GOTUBE_ADMINS = (至少需要配置一个管理员账号)")
_debug: bool = _b("GOTUBE_DEBUG", False)
_log_level: str = _s("GOTUBE_LOG_LEVEL", default="ERROR").upper()
# 登录 Cookie 是否携带 Secure 标记（HTTPS 部署应开启）
_cookie_secure: bool = _b("GOTUBE_COOKIE_SECURE", False)
# 全局 API 速率限制：每 IP 每分钟最大请求数（0=不限制）
_rate_limit: int = _i("GOTUBE_RATE_LIMIT", default=300, min_val=0)
_allow_guest_download: bool = _b("GOTUBE_ALLOW_GUEST_DOWNLOAD", True)
_allow_playlist_download: bool = _b("GOTUBE_ALLOW_PLAYLIST_DOWNLOAD", False)
_max_video_size_mb: int = _i("GOTUBE_MAX_VIDEO_SIZE_MB", required=False, default=0, min_val=0)
_user_storage_quota_mb: int = _i("GOTUBE_USER_STORAGE_QUOTA_MB", required=False, default=0, min_val=0)
_raw_cors_allow_origins: str = _s("GOTUBE_CORS_ALLOW_ORIGINS", default="")
_cors_allow_origins: list[str] = []
for origin in _split_csv(_raw_cors_allow_origins):
    try:
        _cors_allow_origins.append(validate_cors_origin(origin))
    except ValueError as exc:
        _errors.append(f"  GOTUBE_CORS_ALLOW_ORIGINS = '{origin}' ({exc})")
_version: str = (_project_root / "VERSION").read_text(encoding="utf-8").strip() or "0.0.0"

# 静态资源缓存破坏参数：优先用构建产物内容哈希（build.js 生成），
# 内容一变 URL 必变，避免 CDN/浏览器旧缓存；无构建产物时回退版本号
_asset_hash_file = _project_root / _www_dir / "ASSET_HASH"
try:
    _asset_version: str = _asset_hash_file.read_text(encoding="utf-8").strip() or _version
except OSError:
    _asset_version = _version

_china_domains: list[str] = [
    "bilibili.com", "b23.tv", "acfun.cn", "iqiyi.com",
    "youku.com", "qq.com", "douyin.com", "kuaishou.com",
]

# ── 校验 ──

if _errors:
    print(f"[配置错误] 配置文件有误 ({_ENV_FILE}):", file=sys.stderr)
    for err in _errors:
        print(err, file=sys.stderr)
    print()
    print(f"  请修正后重新启动。参考 .env.example 获取模板。", file=sys.stderr)
    sys.exit(1)


# ── 兼容原有的 settings.xxx 访问方式 ──

class _Settings:
    """轻量级配置容器，保持 settings.xxx 访问方式不变"""
    __slots__ = ()

    @property
    def project_root(self) -> Path:
        return _project_root

    @property
    def port(self) -> int:
        return _port

    @property
    def hidden_path(self) -> str:
        return _hidden_path

    @property
    def max_concurrent(self) -> int:
        return _max_concurrent

    @property
    def max_downloads_per_user(self) -> int:
        return _max_downloads_per_user

    @property
    def download_dir(self) -> str:
        return _download_dir

    @property
    def www_dir(self) -> str:
        return _www_dir

    @property
    def cookies_file(self) -> str:
        return _cookies_file

    @property
    def warp_proxy(self) -> str:
        return _warp_proxy

    @property
    def admins(self) -> list[dict[str, str]]:
        return _admins

    @property
    def db_file(self) -> Path:
        p = Path(_db_file)
        return p if p.is_absolute() else _project_root / p

    @property
    def backup_dir(self) -> Path:
        """数据库备份目录（相对路径按项目根解析）"""
        p = Path(_backup_dir)
        return p if p.is_absolute() else _project_root / p

    @property
    def backup_interval_hours(self) -> int:
        """数据库自动备份间隔（小时）"""
        return _backup_interval_hours

    @property
    def backup_retention(self) -> int:
        """数据库备份保留份数"""
        return _backup_retention

    @property
    def debug(self) -> bool:
        return _debug

    @property
    def cookie_secure(self) -> bool:
        """登录 Cookie 是否携带 Secure 标记（仅 HTTPS 传输）"""
        return _cookie_secure

    @property
    def rate_limit(self) -> int:
        """全局 API 速率限制（每 IP 每分钟请求数，0=不限制）"""
        return _rate_limit

    @property
    def log_level(self) -> str:
        return _log_level

    @property
    def allow_guest_download(self) -> bool:
        """是否允许匿名用户下载"""
        return _allow_guest_download

    @property
    def allow_playlist_download(self) -> bool:
        """是否允许播放列表/用户空间URL下载"""
        return _allow_playlist_download

    @property
    def max_video_size_mb(self) -> int:
        """单个视频最大大小限制（MB），0=不限制"""
        return _max_video_size_mb

    @property
    def user_storage_quota_mb(self) -> int:
        """普通用户默认视频库容量限制（MB），0=不限制"""
        return _user_storage_quota_mb

    @property
    def china_domains(self) -> list[str]:
        return _china_domains

    @property
    def version(self) -> str:
        return _version

    @property
    def asset_version(self) -> str:
        return _asset_version

    @property
    def cors_allow_origins(self) -> list[str]:
        return list(_cors_allow_origins)

    def get_download_dir(self) -> Path:
        """获取下载目录的绝对路径"""
        p = Path(_download_dir)
        return p if p.is_absolute() else _project_root / p

    def get_cookies_file(self) -> Path | None:
        """获取 cookies 文件路径（如果存在）"""
        p = Path(_cookies_file)
        if not p.is_absolute():
            p = _project_root / p
        return p if p.exists() else None


# 全局单例（保持 from .config import settings 用法不变）
settings = _Settings()
