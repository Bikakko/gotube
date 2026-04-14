"""
GoTube 配置管理

只从程序目录下的 .env 文件加载配置。
如果 .env 不存在或配置有误，程序会报错退出并输出详细日志。
不读取系统环境变量，确保多实例互不干扰。
"""

import sys
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


# ── 读取所有配置项 ──

_project_root: Path = Path(__file__).parent.parent

_port: int = _i("GOTUBE_PORT", required=True, min_val=1, max_val=65535)
_hidden_path: str = _s("GOTUBE_HIDDEN_PATH", required=True)
_max_concurrent: int = _i("GOTUBE_MAX_CONCURRENT", required=True, min_val=1, max_val=20)
_download_dir: str = _s("GOTUBE_DOWNLOAD_DIR", required=True)
_www_dir: str = _s("GOTUBE_WWW_DIR", default="www")
_cookies_file: str = _s("GOTUBE_COOKIES_FILE")
_warp_proxy: str = _s("GOTUBE_WARP_PROXY")
_db_file: str = _s("GOTUBE_DB_FILE", default="./gotube.db")

# 解析管理员账号列表（格式：用户名1:密码1,用户名2:密码2）
_raw_admins: str = _s("GOTUBE_ADMINS", required=True)
_admins: list[dict[str, str]] = []
if _raw_admins:
    for pair in _raw_admins.split(","):
        pair = pair.strip()
        if not pair:
            continue
        parts = pair.split(":", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            _errors.append(f"  GOTUBE_ADMINS = '{pair}' (格式错误，应为 用户名:密码)")
        else:
            _admins.append({"username": parts[0], "password": parts[1]})

if not _admins:
    _errors.append("  GOTUBE_ADMINS = (至少需要配置一个管理员账号)")
_debug: bool = _b("GOTUBE_DEBUG", False)
_log_level: str = _s("GOTUBE_LOG_LEVEL", default="ERROR").upper()

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
    def debug(self) -> bool:
        return _debug

    @property
    def log_level(self) -> str:
        return _log_level

    @property
    def china_domains(self) -> list[str]:
        return _china_domains

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
