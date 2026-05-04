"""
yt-dlp 下载器封装层

使用文件 SHA256 前 16 位作为文件指纹，确保唯一性。
下载完成后计算 hash，同 hash 文件自动去重。
"""

import asyncio
import binascii
import ipaddress
import json
import logging
import os
import re
import shutil
import socket
import threading
import time
import uuid
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp

from .config import settings
from .cookie_store import get_runtime_cookies_file
from .path_utils import resolve_inside
from .security import validate_guest_session_id

logger = logging.getLogger(__name__)

# 视频文件扩展名集合
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".avi", ".mov"}
DOWNLOAD_ARTIFACT_EXTENSIONS = VIDEO_EXTENSIONS | {".m4a", ".mp3", ".aac", ".opus", ".part", ".ytdl", ".temp"}
YTDLP_VIDEO_FORMAT = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"


class DownloadSizeLimitError(ValueError):
    """下载文件超过单视频大小限制。"""


class DownloadCancelledError(Exception):
    """下载任务被用户或会话生命周期取消。"""


def _is_public_ip_address(ip_text: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_text)
    except ValueError:
        return False
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def is_safe_thumbnail_url(url: str) -> bool:
    """Reject local and private thumbnail URLs to reduce SSRF risk."""
    if not url:
        return False
    try:
        parsed = urlparse(url)
    except ValueError:
        return False

    if parsed.scheme not in {"http", "https"}:
        return False

    hostname = (parsed.hostname or "").strip().lower()
    if not hostname or hostname == "localhost":
        return False

    if _is_public_ip_address(hostname):
        return True

    try:
        infos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except OSError:
        return False

    addresses = {info[4][0] for info in infos if info and info[4]}
    if not addresses:
        return False
    return all(_is_public_ip_address(address) for address in addresses)


def _download_thumbnail(url: str, save_path: Path) -> bool:
    """
    从远程 URL 下载缩略图到本地。

    静默失败，不影响主下载流程。

    Args:
        url: 缩略图远程 URL。
        save_path: 本地保存路径。

    Returns:
        成功返回 True，失败返回 False。
    """
    if not url:
        return False
    if not is_safe_thumbnail_url(url):
        logger.warning("拒绝下载不安全的缩略图 URL: %s", url)
        return False

    try:
        import urllib.request

        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                data = resp.read()
                save_path.parent.mkdir(parents=True, exist_ok=True)
                save_path.write_bytes(data)
                logger.info("缩略图已保存: %s (%d bytes)", save_path.name, len(data))
                return True
            logger.warning("缩略图下载失败 (HTTP %d): %s", resp.status, url)
    except Exception as e:
        logger.warning("下载缩略图失败: %s, 错误: %s", url, e)
    return False


def _read_meta_from_dir(dir_path: Path) -> dict:
    """从目录读取 meta.json 元数据"""
    meta_path = dir_path / "meta.json"
    if not meta_path.exists():
        return {}
    try:
        with open(meta_path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logging.getLogger(__name__).warning("读取元数据失败 %s: %s", meta_path, e)
        return {}


# yt-dlp 进度回调返回的数据结构
ProgressData = dict


class DownloadTask:
    """下载任务数据对象"""

    def __init__(self, task_id: str, url: str, client_id: str) -> None:
        self.task_id = task_id
        self.url = url
        self.source_url = url
        self.original_url = url
        self.client_id = client_id
        self.status = "pending"  # pending | downloading | completed | failed
        self.progress = 0.0
        self.speed = 0.0
        self.eta = 0
        self.filename = ""
        self.filepath = ""
        self.error = ""
        self.created_at = datetime.now(UTC)
        self.completed_at: datetime | None = None
        self.title = ""
        self.thumbnail = ""
        self.duration = 0
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self.download_artifact_path = ""
        self.estimated_size_bytes: int | None = None
        self.download_phase_count = 1
        self.download_phase_index = 0
        self.download_phase_artifacts: list[str] = []
        self.cancel_requested = False
        self.cancel_reason = ""
        self.video_id = ""
        self.file_hash = ""
        self.is_duplicate = False
        self.is_guest = False  # 是否为匿名用户下载
        self.session_id = ""   # 匿名用户会话 ID
        self.owner_user_id: int | None = None
        self.user_video_item_id: int | None = None
        self.media_asset_id: int | None = None
        self.share_token = ""

    def request_cancel(self, reason: str = "下载已取消") -> None:
        """标记任务需要取消，由下载执行阶段负责中断和清理。"""
        self.cancel_requested = True
        self.cancel_reason = reason or "下载已取消"


class Downloader:
    """yt-dlp 下载器"""

    def __init__(
        self,
        download_dir: Path | None = None,
        cookies_file: Path | None = None,
        warp_proxy: str | None = None,
    ) -> None:
        """
        初始化下载器。

        Args:
            download_dir: 下载目录路径，默认使用配置中的路径。
            cookies_file: Cookies 文件路径，用于视频网站认证。
            warp_proxy: WARP SOCKS5 代理地址，用于非中国域名。
        """
        self.download_dir = download_dir or settings.get_download_dir()
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.cookies_file = cookies_file or get_runtime_cookies_file()
        self.warp_proxy = warp_proxy or settings.warp_proxy
        self._tasks: dict[str, DownloadTask] = {}

        # 目录索引缓存：{文件绝对路径: stat 缓存时间}
        self._file_index_cache: dict[str, dict] = {}
        self._file_index_cache_time: float = 0
        # 缓存有效期（秒）
        self._file_index_cache_ttl = 30

        # hash → 文件路径的索引（避免递归搜索）
        self._hash_index: dict[str, Path] = {}
        self._hash_index_lock = threading.Lock()
        self._hash_index_time: float = 0
        self._hash_index_ttl = 30

        # 匿名用户临时下载目录
        self.guest_download_dir = self.download_dir / "temp_guest"
        self.guest_download_dir.mkdir(parents=True, exist_ok=True)

        # 启动时依赖检查
        self._check_dependencies()

        # 启动时清理上次遗留的临时下载文件
        self._cleanup_orphaned_temp_files()

        # 启动时清理过期的 guest session（超过 24 小时）
        self.cleanup_expired_guest_sessions(max_age_hours=24.0)

    def reload_cookies(self, cookies_file: Path | None) -> None:
        """
        热重载 cookies 文件配置。

        Args:
            cookies_file: 新的 cookies 文件路径，None 表示清空。
        """
        old_file = self.cookies_file
        self.cookies_file = cookies_file

        if self.cookies_file and self.cookies_file.exists():
            logger.info("Cookies 文件已热重载: %s -> %s", old_file, self.cookies_file)
        else:
            logger.warning("Cookies 文件已清空（旧值: %s）", old_file)

    def _check_dependencies(self) -> None:
        """检查运行时依赖（ffmpeg、cookies 文件等）"""
        # 1. 检查 ffmpeg
        import shutil as _shutil

        ffmpeg_path = _shutil.which("ffmpeg")
        if ffmpeg_path:
            logger.info("ffmpeg 已就绪: %s", ffmpeg_path)
        else:
            logger.error(
                "ffmpeg 未安装或不在 PATH 中。"
                "视频下载（尤其是分离音视频合并）将失败。"
                "请安装 ffmpeg: https://ffmpeg.org/download.html"
            )

        # 2. 检查 cookies 文件
        if self.cookies_file and self.cookies_file.exists():
            logger.info("Cookies 文件已加载: %s", self.cookies_file)
        else:
            cookie_path_display = self.cookies_file or get_runtime_cookies_file()
            if not cookie_path_display:
                logger.warning(
                    "未配置 Cookies 文件。部分视频站点（如 YouTube）可能需要登录认证。"
                    "如需使用，请在 .env 中配置 GOTUBE_COOKIES_FILE"
                )
            else:
                logger.warning(
                    "Cookies 文件不存在: %s。"
                    "部分视频站点（如 YouTube）可能需要登录认证。",
                    cookie_path_display,
                )

    def _cleanup_orphaned_temp_files(self) -> None:
        """清理下载目录中残留的 temp_* 临时文件和 .temp_ytdlp 目录"""
        count = 0
        # 清理旧的 temp_* 文件（兼容旧代码）
        for f in self.download_dir.iterdir():
            if f.is_file() and f.name.startswith("temp_"):
                try:
                    f.unlink()
                    logger.info("清理残留临时文件: %s", f.name)
                    count += 1
                except OSError as e:
                    logger.warning("删除临时文件失败 %s: %s", f.name, e)
        # 清理 .temp_ytdlp 目录中的残留文件
        temp_dir = self.download_dir / ".temp_ytdlp"
        if temp_dir.exists():
            for f in temp_dir.iterdir():
                if f.is_file():
                    try:
                        f.unlink()
                        logger.info("清理残留临时文件: %s", f.name)
                        count += 1
                    except OSError as e:
                        logger.warning("删除临时文件失败 %s: %s", f.name, e)
        if count:
            logger.info("已清理 %d 个残留临时文件", count)

    def create_task(self, url: str, client_id: str) -> DownloadTask:
        """
        创建下载任务。

        Args:
            url: 视频链接。
            client_id: 客户端标识。

        Returns:
            新创建的 DownloadTask 对象。
        """
        task_id = str(uuid.uuid4())[:8]
        task = DownloadTask(task_id, url, client_id)
        self._tasks[task_id] = task
        return task

    @staticmethod
    def compute_file_hash(filepath: str, chunk_size: int = 65536) -> str:
        """
        计算文件 CRC32，返回 8 位十六进制字符串。

        64KB 分块读取，内存占用极小，计算速度快。

        Args:
            filepath: 文件路径。
            chunk_size: 每次读取的字节数。

        Returns:
            8 位 CRC32 十六进制字符串。
        """
        crc = 0
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                crc = binascii.crc32(chunk, crc) & 0xFFFFFFFF
        return f"{crc:08x}"

    def _build_file_index_cache(self) -> list[dict]:
        """
        构建或返回缓存的文件列表索引。

        返回包含文件信息的字典列表，带 TTL 缓存机制。
        """
        import time

        now = time.time()
        # 检查缓存是否有效
        if self._file_index_cache and (now - self._file_index_cache_time) < self._file_index_cache_ttl:
            return list(self._file_index_cache.values())

        # 重建缓存
        self._file_index_cache.clear()
        for f in self.download_dir.rglob("*"):
            if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS:
                rel_path = f.relative_to(self.download_dir)
                # 跳过 guest 临时文件
                if str(rel_path).startswith("temp_guest/") or str(rel_path).startswith("temp_guest" + os.sep):
                    continue
                abs_path = str(f.resolve())
                stat = f.stat()
                file_info: dict = {
                    "filename": str(rel_path),
                    "filepath": str(f),
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                }
                # 读取同目录下的 meta.json
                meta = _read_meta_from_dir(f.parent)
                if meta:
                    file_info["title"] = meta.get("title", "")
                    file_info["thumbnail"] = meta.get("thumbnail", "")
                    file_info["video_id"] = meta.get("video_id", "")
                    file_info["duration"] = meta.get("duration", 0)
                    file_info["file_hash"] = meta.get("file_hash", "")
                else:
                    # 没有 meta.json 时，从目录名提取 hash
                    parent_name = f.parent.name
                    if "_" in parent_name:
                        file_info["file_hash"] = parent_name.rsplit("_", 1)[-1]

                self._file_index_cache[abs_path] = file_info

        self._file_index_cache_time = now
        return list(self._file_index_cache.values())

    def invalidate_file_index_cache(self) -> None:
        """文件变更时使缓存失效（下载完成/删除后调用）"""
        self._file_index_cache.clear()
        self._file_index_cache_time = 0

    def _build_hash_index(self) -> dict[str, Path]:
        """
        构建 hash → 文件路径的索引（用于 find_hash_file 优化）。

        采用带 TTL 的内存缓存，避免在热点路径上重复递归扫描磁盘。
        """
        now = time.time()
        if self._hash_index and (now - self._hash_index_time) < self._hash_index_ttl:
            return self._hash_index

        with self._hash_index_lock:
            now = time.time()
            if self._hash_index and (now - self._hash_index_time) < self._hash_index_ttl:
                return self._hash_index

            rebuilt_index: dict[str, Path] = {}
            for f in self.download_dir.rglob("*"):
                if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS:
                    rel_path = f.relative_to(self.download_dir)
                    if rel_path.parts and rel_path.parts[0] == "temp_guest":
                        continue
                    parent_name = f.parent.name
                    if "_" in parent_name:
                        file_hash = parent_name.rsplit("_", 1)[-1]
                        rebuilt_index[file_hash] = f

            self._hash_index = rebuilt_index
            self._hash_index_time = now
            return self._hash_index

    def invalidate_hash_index(self) -> None:
        """文件变更时使 hash 索引失效"""
        with self._hash_index_lock:
            self._hash_index.clear()
            self._hash_index_time = 0

    def find_hash_file(self, file_hash: str) -> Path | None:
        """
        根据 hash 前缀从索引中查找已存在的文件。

        Args:
            file_hash: 8 位 hash 前缀。

        Returns:
            匹配的文件路径，未找到返回 None。
        """
        hash_index = self._build_hash_index()
        # 精确匹配
        if file_hash in hash_index:
            path = hash_index[file_hash]
            # 验证文件是否仍然存在（可能已被外部删除）
            if path.is_file():
                return path
            # 文件不存在，从缓存中移除
            logger.warning("hash索引中的文件不存在，已移除: hash=%s, path=%s", file_hash, path)
            hash_index.pop(file_hash, None)
        # 前缀匹配（仅在内存索引中查找，避免再次递归扫描磁盘）
        for indexed_hash, indexed_path in list(hash_index.items()):
            if indexed_hash.startswith(file_hash):
                if indexed_path.is_file():
                    return indexed_path
                logger.warning("hash索引中的文件不存在，已移除: hash=%s, path=%s", indexed_hash, indexed_path)
                hash_index.pop(indexed_hash, None)
                break
        return None

    def get_task(self, task_id: str) -> DownloadTask | None:
        """获取任务信息"""
        return self._tasks.get(task_id)

    def get_tasks_by_client(self, client_id: str) -> list[DownloadTask]:
        """获取指定客户端的所有任务"""
        return [t for t in self._tasks.values() if t.client_id == client_id]

    def cleanup_temp_files(self, task_id: str) -> int:
        """
        清理指定 task_id 的临时缓存文件（.part / 未完成的 temp_*）。

        用于下载失败或取消后清理残留文件，避免重试时冲突。

        Args:
            task_id: 任务 ID。

        Returns:
            清理的文件数量。
        """
        count = 0
        # 清理旧的 temp_* 文件（下载目录）
        for f in self.download_dir.iterdir():
            if f.is_file() and f.name.startswith(f"temp_{task_id}"):
                try:
                    f.unlink()
                    logger.info("清理临时文件: %s", f.name)
                    count += 1
                except OSError as e:
                    logger.warning("删除临时文件失败 %s: %s", f.name, e)
        # 清理 .temp_ytdlp 目录中的文件
        temp_dir = self.download_dir / ".temp_ytdlp"
        if temp_dir.exists():
            for f in temp_dir.iterdir():
                if f.is_file() and f.name.startswith(f"temp_{task_id}"):
                    try:
                        f.unlink()
                        logger.info("清理临时文件: %s", f.name)
                        count += 1
                    except OSError as e:
                        logger.warning("删除临时文件失败 %s: %s", f.name, e)
        if count:
            logger.info("已清理 %d 个临时文件 (task_id=%s)", count, task_id)
        return count

    def _is_download_artifact_path(self, path: Path) -> bool:
        """确认待清理路径仍位于下载根目录内。"""
        try:
            path.resolve().relative_to(self.download_dir.resolve())
            return True
        except ValueError:
            return False

    @staticmethod
    def _artifact_base_name(path: Path) -> str:
        """返回 yt-dlp 分离音视频同一输出族的基础文件名。"""
        name = path.name
        if name.endswith(".part"):
            name = name[:-5]
        stem = Path(name).stem
        return re.sub(r"\.f\d+$", "", stem)

    def _collect_artifact_siblings(self, path: Path) -> set[Path]:
        """收集同一 yt-dlp 输出族的最终文件、音视频分片和 part 文件。"""
        if not path.parent.exists() or not self._is_download_artifact_path(path):
            return set()

        base = self._artifact_base_name(path)
        if not base:
            return set()

        artifacts: set[Path] = set()
        for candidate in path.parent.iterdir():
            if not candidate.is_file():
                continue
            if candidate.suffix.lower() not in DOWNLOAD_ARTIFACT_EXTENSIONS:
                continue
            candidate_base = self._artifact_base_name(candidate)
            if candidate_base == base:
                artifacts.add(candidate)
        return artifacts

    def cleanup_download_artifacts(self, task: DownloadTask, temp_file: str | None = None) -> int:
        """
        清理一次下载可能产生的完整输出族。

        yt-dlp 在 YouTube/Bilibili 等分离音视频场景下可能生成
        title.f137.mp4、title.f140.m4a、title.mp4.part 等同源文件。失败时只删
        temp_file 会留下孤儿音频或 part 文件，所以这里按最终输出前缀成组清理。
        """
        roots: list[Path] = []
        if temp_file:
            roots.append(Path(temp_file))
        if task.filepath:
            roots.append(Path(task.filepath))
        if task.download_artifact_path:
            roots.append(Path(task.download_artifact_path))

        artifacts: set[Path] = set()
        for root in roots:
            if self._is_download_artifact_path(root):
                artifacts.add(root)
                artifacts.update(self._collect_artifact_siblings(root))

        count = 0
        for artifact in artifacts:
            try:
                if artifact.exists() and artifact.is_file() and self._is_download_artifact_path(artifact):
                    artifact.unlink()
                    count += 1
                    logger.info("清理下载残留文件: %s", artifact)
            except OSError as e:
                logger.warning("清理下载残留文件失败 %s: %s", artifact, e)
        return count

    def cleanup_guest_session(self, session_id: str) -> int:
        """
        清理指定 session 的所有匿名用户临时文件。

        Args:
            session_id: 匿名用户会话 ID。

        Returns:
            清理的目录数量。
        """
        try:
            session_id = validate_guest_session_id(session_id)
            session_dir = resolve_inside(self.guest_download_dir, session_id)
        except Exception as e:
            logger.warning("非法 guest session，跳过清理: %s, error=%s", session_id, e)
            return 0
        if not session_dir.exists():
            logger.info("Guest session 目录不存在，无需清理: %s", session_id)
            return 0

        count = 0
        try:
            # 删除整个 session 目录
            if session_dir == self.guest_download_dir.resolve():
                logger.warning("拒绝清理 guest 根目录: %s", session_dir)
                return 0
            shutil.rmtree(session_dir)
            logger.info("已清理 guest session 临时文件: %s", session_id)
            count += 1
        except OSError as e:
            logger.warning("清理 guest session 失败 %s: %s", session_id, e)

        # 尝试清理空的 guest_download_dir
        try:
            if self.guest_download_dir.exists() and not any(self.guest_download_dir.iterdir()):
                self.guest_download_dir.rmdir()
                logger.info("guest_download_dir 为空，已删除")
        except OSError:
            pass

        return count

    def cleanup_expired_guest_sessions(self, max_age_hours: float = 24.0) -> int:
        """
        启动时清理过期的 guest session（超过指定时间的目录）。

        Args:
            max_age_hours: 最大保留时长（小时）。

        Returns:
            清理的 session 数量。
        """
        if not self.guest_download_dir.exists():
            return 0

        import time
        now = time.time()
        max_age_seconds = max_age_hours * 3600
        count = 0

        for session_dir in self.guest_download_dir.iterdir():
            if session_dir.is_dir():
                try:
                    stat = session_dir.stat()
                    # 使用最后修改时间判断
                    if now - stat.st_mtime > max_age_seconds:
                        shutil.rmtree(session_dir)
                        logger.info("清理过期 guest session: %s (最后修改: %s)",
                                   session_dir.name,
                                   datetime.fromtimestamp(stat.st_mtime).isoformat())
                        count += 1
                except OSError as e:
                    logger.warning("清理过期 guest session 失败 %s: %s", session_dir.name, e)

        if count > 0:
            logger.info("已清理 %d 个过期 guest session", count)

        return count

    def get_guest_download_count(self, session_id: str) -> int:
        """
        获取指定 session 下已完成的视频数量。

        Args:
            session_id: 游客 session ID。

        Returns:
            视频文件数量。
        """
        try:
            session_id = validate_guest_session_id(session_id)
            session_dir = resolve_inside(self.guest_download_dir, session_id)
        except Exception as e:
            logger.warning("非法 guest session，无法统计: %s, error=%s", session_id, e)
            return 0
        if not session_dir.exists():
            return 0

        count = 0
        for f in session_dir.rglob("*"):
            if f.is_file() and not f.is_symlink() and f.suffix.lower() in VIDEO_EXTENSIONS:
                count += 1

        return count

    def _move_or_copy_guest_item(self, item: Path, target_item: Path) -> None:
        """Move a guest transfer item, falling back to copy when Windows locks the source."""
        try:
            shutil.move(str(item), str(target_item))
            return
        except OSError as move_error:
            logger.warning(
                "移动 guest 文件失败，尝试复制兜底: %s -> %s, error=%s",
                item,
                target_item,
                move_error,
            )

        if item.is_dir():
            shutil.copytree(item, target_item, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target_item)

    def transfer_guest_session(self, session_id: str, client_id: str | None = None) -> dict:
        """
        将游客 session 下的所有视频转移到主下载目录。

        Args:
            session_id: 游客 session ID。
            client_id: 客户端标识（可选，用于返回更新后的任务数据）。

        Returns:
            转移结果字典，包含转移数量、文件列表和更新后的任务数据。

        Raises:
            ValueError: 如果 session 不存在或没有视频。
        """
        try:
            session_id = validate_guest_session_id(session_id)
            session_dir = resolve_inside(self.guest_download_dir, session_id)
        except Exception as e:
            raise ValueError("非法 session_id") from e

        duplicate_files: list[str] = []
        if client_id:
            for task in self.get_tasks_by_client(client_id):
                if task.is_guest and task.session_id == session_id and task.filename and "/DUPLICATE/" in task.filename:
                    duplicate_files.append(task.filename.split("/DUPLICATE/", 1)[1])

        if not session_dir.exists() and not duplicate_files:
            raise ValueError(f"游客 session 不存在: {session_id}")

        # 收集所有视频文件
        video_files = []
        if session_dir.exists():
            for f in session_dir.rglob("*"):
                if f.is_file() and not f.is_symlink() and f.suffix.lower() in VIDEO_EXTENSIONS:
                    video_files.append(f)

        if not video_files and not duplicate_files:
            raise ValueError("该 session 下没有视频文件")

        transferred = list(dict.fromkeys(duplicate_files))
        errors = []

        for video_file in video_files:
            try:
                # 构造目标路径：直接使用原有的目录结构
                # 从 temp_guest/{session_id}/{title}_{hash}/{hash}.mp4
                # 转移到 {title}_{hash}/{hash}.mp4
                relative_to_session = video_file.relative_to(session_dir)
                # relative_to_session 类似: "{title}_{hash}/{hash}.mp4"
                target_path = resolve_inside(self.download_dir, relative_to_session)
                video_dir = video_file.parent

                # 检查目标是否已存在（避免重复转移）
                if target_path.exists():
                    logger.info("目标文件已存在，跳过: %s", target_path)
                    transferred.append(str(relative_to_session))
                    try:
                        shutil.rmtree(video_dir)
                        logger.info("删除已转存重复 guest 目录: %s", video_dir)
                    except OSError as e:
                        logger.warning("删除重复 guest 目录失败 %s: %s", video_dir, e)
                    continue

                # 获取视频所在目录（包含 meta.json 和缩略图）

                # 创建目标目录
                target_path.parent.mkdir(parents=True, exist_ok=True)

                # 移动整个目录（视频 + meta.json + 缩略图）
                if video_dir.exists():
                    # 使用 shutil.move 移动整个目录
                    target_dir = target_path.parent
                    if target_dir.exists():
                        # 目标目录已存在，逐个移动文件
                        for item in video_dir.iterdir():
                            target_item = resolve_inside(target_dir, item.name)
                            if not target_item.exists():
                                self._move_or_copy_guest_item(item, target_item)
                                logger.info("转移文件: %s -> %s", item.name, target_dir)
                            else:
                                logger.info("目标文件已存在，跳过: %s", target_item)
                    else:
                        self._move_or_copy_guest_item(video_dir, target_dir)
                        logger.info("转移目录: %s -> %s", video_dir.name, target_dir.parent)

                    try:
                        if video_dir.exists():
                            shutil.rmtree(video_dir)
                    except OSError as e:
                        logger.warning("guest 源目录暂时无法删除，后续过期清理会重试 %s: %s", video_dir, e)

                    transferred.append(str(relative_to_session))
                else:
                    logger.warning("视频目录不存在: %s", video_dir)

            except Exception as e:
                logger.error("转移文件失败 %s: %s", video_file, e)
                errors.append({"file": str(video_file), "error": str(e)})

        # 清理空的 session 目录
        try:
            if session_dir.exists():
                # 删除空的子目录
                for sub_dir in session_dir.iterdir():
                    if sub_dir.is_dir() and not any(sub_dir.iterdir()):
                        sub_dir.rmdir()
                        logger.info("删除空子目录: %s", sub_dir)

                # 如果 session 目录为空，删除它
                if not any(session_dir.iterdir()):
                    session_dir.rmdir()
                    logger.info("session 目录已清空，已删除: %s", session_dir)
        except OSError as e:
            logger.warning("清理 session 目录失败 %s: %s", session_dir, e)

        # 使缓存失效
        self.invalidate_file_index_cache()
        self.invalidate_hash_index()

        # 如果提供了 client_id，获取更新后的任务数据
        updated_tasks = []
        if client_id:
            tasks = self.get_tasks_by_client(client_id)
            for task in tasks:
                # 将 guest 任务的 filename 更新为新路径
                if task.is_guest and task.session_id == session_id and task.filename:
                    # 检查是否为去重文件（DUPLICATE/ 标记）
                    if '/DUPLICATE/' in task.filename:
                        # 去重文件：文件已在主视频库，只需移除游客标识
                        # 提取 DUPLICATE/ 后面的实际路径
                        actual_path = task.filename.split('/DUPLICATE/', 1)[1]
                        task.filename = actual_path
                        task.is_guest = False
                        task.session_id = ""
                        logger.info("去重文件转移（文件已在主库）: %s", actual_path)
                    else:
                        # 普通文件：去掉 temp_guest/{session_id}/ 前缀
                        task.filename = task.filename.replace(f"temp_guest/{session_id}/", "")
                        task.is_guest = False
                        task.session_id = ""
                
                # 转换为字典格式
                task_dict = {
                    "task_id": task.task_id,
                    "url": task.url,
                    "status": task.status,
                    "progress": task.progress,
                    "speed": task.speed,
                    "eta": task.eta,
                    "filename": task.filename,
                    "error": task.error,
                    "title": task.title,
                    "thumbnail": task.thumbnail,
                    "duration": task.duration,
                    "video_id": task.video_id,
                    "file_hash": task.file_hash,
                    "is_duplicate": task.is_duplicate,
                    "created_at": task.created_at.isoformat(),
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                }
                updated_tasks.append(task_dict)

        result = {
            "status": "ok",
            "session_id": session_id,
            "transferred_count": len(transferred),
            "transferred_files": transferred,
            "errors": errors,
            "updated_tasks": updated_tasks,
        }

        logger.info("游客视频转移完成: session=%s, 转移=%d, 错误=%d",
                   session_id, len(transferred), len(errors))

        return result

    def retry_task(self, task: DownloadTask, progress_callback: Callable) -> asyncio.Task:
        """
        重试下载：重置任务状态 → 清理缓存 → 重新下载。

        Args:
            task: 下载任务对象。
            progress_callback: 异步进度回调函数。

        Returns:
            下载协程的 Task 对象。
        """
        # 重置任务状态
        task.status = "pending"
        task.progress = 0.0
        task.speed = 0.0
        task.eta = 0
        task.filename = ""
        task.filepath = ""
        task.error = ""
        task.file_hash = ""
        task.is_duplicate = False
        task.completed_at = None
        task.downloaded_bytes = 0
        task.total_bytes = 0
        task.download_artifact_path = ""
        task.estimated_size_bytes = None

        # 清理残留临时文件
        self.cleanup_temp_files(task.task_id)

        # 启动下载协程
        return asyncio.create_task(self.download(task, progress_callback), name=f"retry-{task.task_id}")

    def delete_task(self, task_id: str) -> bool:
        """删除任务记录"""
        if task_id in self._tasks:
            del self._tasks[task_id]
            return True
        return False

    def get_active_tasks(self) -> list[DownloadTask]:
        """获取所有活跃（pending/downloading）的任务"""
        return [t for t in self._tasks.values() if t.status in ("pending", "downloading")]

    def count_by_status(self, status: str) -> int:
        """
        统计指定状态的任务数量。

        Args:
            status: 任务状态（pending, downloading, completed, failed）。

        Returns:
            匹配状态的任务数量。
        """
        return sum(1 for t in self._tasks.values() if t.status == status)

    def _is_china_domain(self, url: str) -> bool:
        """判断 URL 是否来自中国域名"""
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname or ""
            for domain in settings.china_domains:
                if hostname == domain or hostname.endswith("." + domain):
                    return True
        except Exception as e:
            logger.warning("域名判断失败: %s", e)
        return False

    def _get_proxy_for_url(self, url: str) -> str | None:
        """根据 URL 决定是否使用代理"""
        if self._is_china_domain(url):
            logger.debug("中国域名，不使用代理: %s", url)
            return None
        # WARP 已停用，所有域名直连
        logger.debug("非中国域名，直连: %s", url)
        return None

    def _build_base_opts(self, url: str) -> dict:
        """构建 yt-dlp 基础配置"""
        opts: dict = {
            "js_runtimes": {"node": {}},
            "remote_components": "ejs:github",
            "noplaylist": True,
        }
        proxy = self._get_proxy_for_url(url)
        if proxy:
            opts["proxy"] = proxy
        if self.cookies_file:
            opts["cookiefile"] = str(self.cookies_file)
        return opts

    @staticmethod
    def _known_format_size(fmt: dict) -> int | None:
        """读取 yt-dlp 格式记录中的已知大小。"""
        size = fmt.get("filesize") or fmt.get("filesize_approx")
        if not size:
            return None
        try:
            size_int = int(size)
        except (TypeError, ValueError):
            return None
        return size_int if size_int > 0 else None

    def _estimate_selected_download_size(self, info: dict) -> int | None:
        """
        估算当前 yt-dlp 选择结果的总大小。

        分离音视频时优先汇总 requested_formats；如果其中任一流大小未知，
        返回 None，避免用不完整估算误拒绝下载。
        """
        requested_formats = info.get("requested_formats")
        if isinstance(requested_formats, list) and requested_formats:
            sizes = [self._known_format_size(fmt) for fmt in requested_formats]
            if all(size is not None for size in sizes):
                return sum(size for size in sizes if size is not None)
            return None

        return self._known_format_size(info)

    @staticmethod
    def _format_size_limit_error(actual_size: int, limit: int, *, estimated: bool) -> str:
        actual_mb = actual_size / 1024 / 1024
        limit_mb = limit / 1024 / 1024
        prefix = "预计视频文件大小超过限制" if estimated else "视频文件超过大小限制"
        return f"{prefix}：{actual_mb:.2f} MB / {limit_mb:.2f} MB"

    def _size_limit_bytes(self, max_size_bytes: int | None = None) -> int | None:
        if max_size_bytes is not None:
            return max_size_bytes if max_size_bytes > 0 else None
        if settings.max_video_size_mb <= 0:
            return None
        return settings.max_video_size_mb * 1024 * 1024

    def _enforce_preflight_size_limit(self, info: dict, max_size_bytes: int | None = None) -> None:
        """下载前用 yt-dlp 提取结果预判最终文件大小。"""
        limit = self._size_limit_bytes(max_size_bytes)
        if not limit:
            return
        estimate = self._estimate_selected_download_size(info)
        if estimate is None:
            return
        if estimate > limit:
            raise DownloadSizeLimitError(self._format_size_limit_error(estimate, limit, estimated=True))

    def _artifact_family_size(self, path: Path) -> int:
        """统计同一输出族当前已落盘大小。"""
        artifacts = self._collect_artifact_siblings(path)
        if self._is_download_artifact_path(path):
            artifacts.add(path)
        total = 0
        for artifact in artifacts:
            try:
                if artifact.exists() and artifact.is_file():
                    total += artifact.stat().st_size
            except OSError:
                continue
        return total

    def _enforce_active_size_limit(
        self,
        filepath: str | None,
        downloaded_bytes: int,
        max_size_bytes: int | None = None,
    ) -> None:
        """下载中按同一输出族已落盘大小执行保护。"""
        limit = self._size_limit_bytes(max_size_bytes)
        if not limit:
            return

        actual_size = 0
        if filepath:
            actual_size = self._artifact_family_size(Path(filepath))
        if actual_size <= 0:
            actual_size = downloaded_bytes or 0
        if actual_size > limit:
            raise DownloadSizeLimitError(self._format_size_limit_error(actual_size, limit, estimated=False))

    def _check_playlist_url(self, info: dict, url: str) -> None:
        """
        检查 URL 是否为播放列表/用户空间等多视频链接。
        
        如果配置禁止播放列表下载且检测到多视频链接，抛出异常。
        
        Args:
            info: yt-dlp 提取的视频信息字典。
            url: 原始 URL。
            
        Raises:
            ValueError: 当禁止播放列表下载且检测到多视频时抛出。
        """
        # 如果允许播放列表下载，直接返回
        if settings.allow_playlist_download:
            return
        
        entry_type = info.get("_type")
        
        # 情况1：明确标记为 playlist
        if entry_type == "playlist":
            n_entries = info.get("n_entries")
            if n_entries is None:
                entries = info.get("entries")
                n_entries = len(entries) if entries else 0
            
            if n_entries > 1:
                raise ValueError(
                    f"不支持播放列表或用户空间URL（包含 {n_entries} 个视频）。"
                    f"请提交单个视频链接。"
                )
        
        # 情况2：有 entries 字段但 _type 不是 playlist（某些 extractor 行为）
        elif info.get("entries") and len(info["entries"]) > 1:
            n_entries = len(info["entries"])
            raise ValueError(
                f"检测到多视频链接（包含 {n_entries} 个视频）。"
                f"请提交单个视频链接。"
            )

    def _save_metadata(self, dir_path: Path, task: DownloadTask) -> None:
        """保存视频元数据到 meta.json"""
        meta = {
            "title": task.title,
            "thumbnail": task.thumbnail,
            "video_id": task.video_id,
            "duration": task.duration,
            "file_hash": task.file_hash,
            "url": task.source_url,
            "original_url": task.original_url,
            "tags": [],
            "created_at": datetime.now(UTC).isoformat(),
        }
        meta_path = dir_path / "meta.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        logger.info("元数据已保存: %s", meta_path)

    @staticmethod
    def _verify_file_integrity(filepath: str, task: DownloadTask) -> None:
        """
        验证下载文件的完整性（检查是否同时包含视频和音频流）。

        对 Bilibili 等使用 DASH 格式的网站尤为重要，因为视频和音频
        是分开下载的，ffmpeg 合并失败可能导致缺少音频。

        Args:
            filepath: 文件路径。
            task: 下载任务对象（用于记录警告信息）。
        """
        try:
            import subprocess

            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "error",
                    "-show_entries", "stream=codec_type",
                    "-of", "csv=p=0",
                    filepath,
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            streams = result.stdout.strip().lower()
            has_video = "video" in streams
            has_audio = "audio" in streams

            if has_video and not has_audio:
                logger.warning(
                    "[DEBUG] 文件完整性检查: 文件缺少音频流，可能为无声视频 — %s",
                    filepath,
                )
                task.error = "下载完成但文件缺少音频流，可能网络不稳定"
            elif has_audio and not has_video:
                logger.warning(
                    "[DEBUG] 文件完整性检查: 文件缺少视频流 — %s",
                    filepath,
                )
                task.error = "下载完成但文件缺少视频流，可能网络不稳定"
            elif not has_video and not has_audio:
                logger.warning(
                    "[DEBUG] 文件完整性检查: 文件无可识别的流 — %s",
                    filepath,
                )
                task.error = "下载完成但文件无法识别，可能下载不完整"
            else:
                logger.debug("文件完整性检查: 通过（包含视频+音频流）")
        except subprocess.TimeoutExpired:
            logger.warning("[DEBUG] 文件完整性检查超时")
        except FileNotFoundError:
            logger.debug("ffprobe 未安装，跳过文件完整性检查")
        except Exception as e:
            logger.warning("[DEBUG] 文件完整性检查失败: %s", e)

    def _make_progress_hook(self, task: DownloadTask, max_size_bytes: int | None = None) -> Callable:
        """创建 yt-dlp 进度回调钩子"""

        def phase_progress(downloaded: int, total: int) -> float:
            phase_count = max(1, int(task.download_phase_count or 1))
            phase_index = max(1, int(task.download_phase_index or 1))
            current_ratio = (downloaded / total) if total > 0 else 0.0
            return min((((phase_index - 1) + current_ratio) / phase_count) * 100, 99.9)

        def normalize_artifact_key(d: dict) -> str:
            artifact_path = d.get("filename") or d.get("tmpfilename") or ""
            if not artifact_path:
                return ""
            try:
                normalized = Path(artifact_path).resolve()
            except OSError:
                normalized = Path(artifact_path)
            if normalized.suffix in {".part", ".temp", ".ytdl"}:
                normalized = normalized.with_suffix("")
            return str(normalized)

        def update_phase_tracking(d: dict) -> None:
            artifact_key = normalize_artifact_key(d)
            if not artifact_key:
                return
            if artifact_key not in task.download_phase_artifacts:
                task.download_phase_artifacts.append(artifact_key)
            task.download_phase_index = task.download_phase_artifacts.index(artifact_key) + 1

        def hook(d: dict) -> None:
            try:
                if task.cancel_requested:
                    raise DownloadCancelledError(task.cancel_reason or "下载已取消")

                if d["status"] == "downloading":
                    update_phase_tracking(d)
                    downloaded = d.get("downloaded_bytes", 0)
                    total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                    speed = d.get("speed") or 0
                    eta = d.get("eta") or 0
                    artifact_path = d.get("filename") or d.get("tmpfilename") or ""
                    if artifact_path:
                        task.download_artifact_path = artifact_path

                    if total > 0:
                        task.progress = phase_progress(downloaded, total)
                    elif downloaded > 0 and speed > 0:
                        estimated_total = max(downloaded + speed * eta, downloaded * 1.5) if eta > 0 else downloaded * 2
                        if estimated_total > 0:
                            task.progress = min(phase_progress(downloaded, estimated_total), 95)
                    elif downloaded > 0:
                        task.progress = max(task.progress, 5.0)

                    task.speed = speed
                    task.eta = eta
                    task.downloaded_bytes = downloaded
                    task.total_bytes = total
                    self._enforce_active_size_limit(artifact_path, downloaded, max_size_bytes=max_size_bytes)

                elif d["status"] == "finished":
                    update_phase_tracking(d)
                    phase_count = max(1, int(task.download_phase_count or 1))
                    phase_index = max(1, int(task.download_phase_index or 1))
                    task.progress = min((phase_index / phase_count) * 100, 100.0)
                    task.speed = 0
                    task.eta = 0
            except (DownloadSizeLimitError, DownloadCancelledError):
                raise
            except Exception as e:
                logger.warning("进度回调异常: %s", e)

        return hook

    async def _extract_info(self, url: str, task: DownloadTask) -> dict:
        """
        第一阶段：只提取视频信息，不下载。

        Args:
            url: 视频链接。
            task: 下载任务对象。

        Returns:
            yt-dlp 提取的视频信息字典。
        """
        opts = self._build_base_opts(url)
        opts.update(
            {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "format": YTDLP_VIDEO_FORMAT,
                "merge_output_format": "mp4",
            }
        )

        logger.debug("第一阶段：提取视频信息")
        logger.debug("URL: %s", url)
        logger.debug("yt-dlp opts (keys): %s", list(opts.keys()))

        # 在线程池中执行同步的 yt-dlp 调用，加超时兜底
        loop = asyncio.get_event_loop()

        def _extract() -> dict:
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)

        info = await asyncio.wait_for(
            loop.run_in_executor(None, _extract),
            timeout=7200,  # 2 小时超时兜底
        )

        # 检查是否为播放列表/多视频链接
        self._check_playlist_url(info, url)

        task.video_id = info.get("id", "")
        task.title = info.get("title", "")
        task.thumbnail = info.get("thumbnail", "")
        task.duration = info.get("duration", 0)
        requested_formats = info.get("requested_formats")
        if isinstance(requested_formats, list) and requested_formats:
            task.download_phase_count = len(requested_formats)
        else:
            task.download_phase_count = 1
        task.download_phase_index = 0
        task.download_phase_artifacts = []
        task.estimated_size_bytes = self._estimate_selected_download_size(info)
        self._enforce_preflight_size_limit(info)

        logger.debug("提取成功 - title: %s, video_id: %s, duration: %s", task.title, task.video_id, task.duration)
        logger.debug("缩略图 URL: %s", task.thumbnail)
        logger.debug("信息提取完成: %s", task.title[:50] if task.title else "(空)")
        return info

    async def _do_download(self, url: str, task: DownloadTask,
                           progress_callback: Callable | None = None) -> str | None:
        """
        第二阶段：实际下载视频，期间定期推送进度。

        Args:
            url: 视频链接。
            task: 下载任务对象。
            progress_callback: 异步进度回调函数。

        Returns:
            下载的文件路径，失败返回 None。
        """
        # 无回调时，直接执行下载
        if progress_callback is None:
            return await self._do_download_impl(url, task)

        # 有回调时，启动定期推送任务。不能只按百分比节流：
        # 分离音视频或未知总大小时，字节数会变化但百分比可能长期不变。
        stop_event = asyncio.Event()
        last_progress = task.progress
        last_downloaded = task.downloaded_bytes
        last_push_at = 0.0

        async def push_once() -> bool:
            try:
                await progress_callback(task)
                return True
            except Exception as e:
                logger.debug("下载进度推送失败，继续下载: %s", e)
                return False

        async def push_progress():
            nonlocal last_progress, last_downloaded, last_push_at
            try:
                while not stop_event.is_set():
                    now = time.monotonic()
                    progress_changed = abs(task.progress - last_progress) >= 1.0
                    bytes_changed = task.downloaded_bytes != last_downloaded
                    heartbeat_due = now - last_push_at >= 1.0
                    should_push = task.status == "downloading" and (
                        progress_changed or bytes_changed or heartbeat_due
                    )
                    if should_push:
                        if await push_once():
                            last_progress = task.progress
                            last_downloaded = task.downloaded_bytes
                            last_push_at = now
                    await asyncio.sleep(0.2)  # 200ms间隔
            except asyncio.CancelledError:
                pass

        pusher = asyncio.create_task(push_progress())

        try:
            if await push_once():
                last_progress = task.progress
                last_downloaded = task.downloaded_bytes
                last_push_at = time.monotonic()
            return await self._do_download_impl(url, task)
        finally:
            stop_event.set()
            pusher.cancel()
            with suppress(asyncio.CancelledError):
                await pusher
            await push_once()

    async def _do_download_impl(self, url: str, task: DownloadTask) -> str | None:
        """实际执行 yt-dlp 下载的底层方法"""
        opts = self._build_base_opts(url)
        opts.update(
            {
                "paths": {
                    "home": str(self.download_dir),  # 临时文件和最终文件同目录，由 yt-dlp 自行管理
                    "temp": str(self.download_dir),
                },
                # 使用视频 ID 作为临时文件名，避免推文等长标题导致
                # Windows/ Linux 文件名超长 (Errno 36: File name too long)
                "outtmpl": "%(id)s.%(ext)s",
                "progress_hooks": [self._make_progress_hook(task)],
                "quiet": False,
                "no_warnings": False,
                "merge_output_format": "mp4",
                "format": YTDLP_VIDEO_FORMAT,
                "retries": 3,
                "fragment_retries": 3,
                # ffmpeg 详细错误日志，便于排查合并失败原因
                "postprocessor_args": {
                    "ffmpeg": ["-v", "error"],
                },
            }
        )

        if settings.max_video_size_mb > 0:
            logger.debug(
                "最终合并文件大小限制: %d MB (%d 字节)",
                settings.max_video_size_mb,
                settings.max_video_size_mb * 1024 * 1024,
            )

        logger.debug("第二阶段：开始下载视频")
        logger.debug("download_dir: %s", self.download_dir)
        logger.debug("format: %s", opts.get("format"))

        loop = asyncio.get_event_loop()

        def _download() -> str | None:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                logger.debug("yt-dlp 下载完成,开始解析文件路径")
                
                # 使用 yt-dlp 官方方法生成最终文件路径
                # 注意：当使用 paths 时，prepare_filename 会返回最终路径
                final_path = ydl.prepare_filename(info)
                logger.debug("prepare_filename 返回: %s", final_path)
                logger.debug("文件是否存在: %s", Path(final_path).exists())
                
                if Path(final_path).exists():
                    file_size = Path(final_path).stat().st_size
                    logger.debug("文件存在,大小: %.2f MB", file_size / 1024 / 1024)
                    return final_path
                
                # 如果 prepare_filename 不准确，尝试从 info 获取
                logger.debug("prepare_filename 路径不存在,尝试 requested_downloads fallback")
                requested_downloads = info.get("requested_downloads")
                logger.debug("requested_downloads: %s", requested_downloads is not None)
                
                if requested_downloads:
                    for i, dl_info in enumerate(requested_downloads):
                        dl_path = dl_info.get("filepath")
                        logger.debug("requested_downloads[%d] filepath: %s", i, dl_path)
                        if dl_path:
                            exists = Path(dl_path).exists()
                            logger.debug("文件是否存在: %s", exists)
                            if exists:
                                file_size = Path(dl_path).stat().st_size
                                logger.debug("文件大小: %.2f MB", file_size / 1024 / 1024)
                                return dl_path
                
                logger.error("下载完成但文件不存在! final_path: %s", final_path)
                logger.error("info 中的 __finaldir: %s", info.get("__finaldir", "未设置"))
                logger.error("info 中的 __files_to_move: %s", info.get("__files_to_move", {}))
                return None

        return await asyncio.wait_for(
            loop.run_in_executor(None, _download),
            timeout=7200,  # 2 小时超时兜底
        )

    def _enforce_final_size_limit(self, filepath: str, max_size_bytes: int | None = None) -> None:
        """按最终合并文件大小执行单视频限制。"""
        limit = self._size_limit_bytes(max_size_bytes)
        if not limit:
            return

        path = Path(filepath)
        if not path.exists():
            return

        size = path.stat().st_size
        if size > limit:
            raise DownloadSizeLimitError(self._format_size_limit_error(size, limit, estimated=False))

    async def _post_process(self, temp_file: str, task: DownloadTask) -> tuple[str, str]:
        """
        下载后处理：计算 hash、去重、移动到最终目录。

        Args:
            temp_file: 临时文件路径。
            task: 下载任务对象。

        Returns:
            (最终文件名, 最终文件路径) 元组。

        Raises:
            FileExistsError: 如果是重复文件。
            FileNotFoundError: 如果临时文件不存在。
        """
        logger.debug("第三阶段：后处理开始")
        logger.debug("输入的 temp_file: %s", temp_file)
        logger.debug("temp_file 是否存在: %s", Path(temp_file).exists())
        
        if not Path(temp_file).exists():
            logger.error("temp_file 不存在! 后处理失败!")
            raise FileNotFoundError(f"临时文件不存在: {temp_file}")
        
        # 计算文件 hash
        file_hash = self.compute_file_hash(temp_file)
        task.file_hash = file_hash
        logger.debug("文件 hash: %s", file_hash)

        # 检查是否已存在相同 hash 的文件（内容去重）
        existing = self.find_hash_file(file_hash)
        logger.debug("检查去重 - existing: %s", existing)
        if existing:
            logger.debug("发现重复文件,删除 temp_file")
            os.remove(temp_file)
            task.is_duplicate = True
            rel_path = existing.relative_to(self.download_dir)
            # 游客任务保留 temp_guest/ 前缀，但添加 DUPLICATE/ 标记
            # filepath 指向主视频库的已存在文件
            if task.is_guest:
                task.filename = f"temp_guest/{task.session_id}/DUPLICATE/{rel_path}"
            else:
                task.filename = str(rel_path)
            task.filepath = str(existing)
            logger.debug("文件已存在（去重）: %s", rel_path)
            raise FileExistsError(f"重复文件: {existing}")

        ext = Path(temp_file).suffix or ".mp4"
        logger.debug("文件扩展名: %s", ext)

        # 清理标题中的非法文件名字符，并限制长度避免超出文件系统限制
        safe_title = ""
        if task.title:
            safe_title = "".join(c for c in task.title if c not in r'\/:*?"<>|').strip()
        if len(safe_title) > 40:
            safe_title = safe_title[:40]
        logger.debug("safe_title (清理后): %s", safe_title)

        if not safe_title:
            safe_title = file_hash
            logger.debug("safe_title 为空,使用 hash 作为标题")

        # 根据是否为匿名用户决定目录路径
        if task.is_guest and task.session_id:
            session_id = validate_guest_session_id(task.session_id)
            base_dir = resolve_inside(self.guest_download_dir, session_id)
            base_dir.mkdir(parents=True, exist_ok=True)
        else:
            base_dir = self.download_dir

        # 构造目录名：标题_指纹
        dir_name = f"{safe_title}_{file_hash}"
        dir_path = base_dir / dir_name
        logger.debug("目标目录: %s, base_dir: %s", dir_path, base_dir)

        # 检查同名冲突
        if dir_path.exists():
            logger.debug("目录已存在,检查冲突")
            existing_in_dir = dir_path / f"{file_hash}{ext}"
            if existing_in_dir.exists():
                logger.debug("发现同名同 hash 文件,删除 temp_file")
                os.remove(temp_file)
                task.is_duplicate = True
                if task.is_guest:
                    task.filename = f"temp_guest/{task.session_id}/{dir_name}/{file_hash}{ext}"
                else:
                    task.filename = f"{dir_name}/{file_hash}{ext}"
                task.filepath = str(existing_in_dir)
                raise FileExistsError(f"重复文件: {existing_in_dir}")

            # 同名不同内容，加序号
            i = 1
            while True:
                new_dir_name = f"{safe_title}_{i}_{file_hash}"
                new_dir_path = base_dir / new_dir_name
                logger.debug("尝试新目录名: %s", new_dir_name)
                if not new_dir_path.exists():
                    dir_name = new_dir_name
                    dir_path = new_dir_path
                    break
                i += 1

        # 创建子目录
        dir_path.mkdir(exist_ok=True)
        logger.debug("创建目录: %s", dir_path)

        # 移动文件到子目录
        final_name = f"{file_hash}{ext}"
        final_path = dir_path / final_name
        logger.debug("移动文件: %s -> %s", temp_file, final_path)
        shutil.move(temp_file, str(final_path))
        logger.debug("文件移动完成")

        # 验证文件完整性（检查是否同时包含视频和音频流）
        await asyncio.to_thread(self._verify_file_integrity, str(final_path), task)

        # 下载缩略图到本地（静默失败，不影响主流程）
        if task.thumbnail:
            logger.debug("开始下载缩略图: %s", task.thumbnail)
            thumb_ext = Path(urlparse(task.thumbnail).path).suffix or ".jpg"
            thumb_local_name = f"thumbnail{thumb_ext}"
            thumb_path = dir_path / thumb_local_name
            if await asyncio.to_thread(_download_thumbnail, task.thumbnail, thumb_path):
                task.thumbnail = thumb_local_name  # 保存相对路径
                logger.debug("缩略图下载成功: %s", thumb_local_name)
            else:
                logger.warning("[DEBUG] 缩略图下载失败，保留远程 URL: %s", task.thumbnail)

        # 保存元数据
        self._save_metadata(dir_path, task)

        if task.is_guest:
            task.filename = f"temp_guest/{task.session_id}/{dir_name}/{final_name}"
        else:
            task.filename = f"{dir_name}/{final_name}"
        task.filepath = str(final_path)

        logger.debug("后处理完成 - filename: %s, filepath: %s", task.filename, task.filepath)
        logger.debug("第三阶段：后处理结束")
        return task.filename, str(final_path)

    async def download(self, task: DownloadTask, progress_callback: Callable) -> None:
        """
        执行两阶段下载：先提取信息，再下载，最后后处理。

        Args:
            task: 下载任务对象。
            progress_callback: 进度回调函数，签名为 async callback(task: DownloadTask)。
        """
        task.status = "downloading"
        logger.debug("========================================")
        logger.debug("下载任务开始 - task_id: %s, url: %s", task.task_id, task.url)
        logger.debug("========================================")

        temp_file: str | None = None
        try:
            # 第一阶段：提取信息
            logger.debug("进入第一阶段：信息提取")
            await self._extract_info(task.url, task)
            await progress_callback(task)
            logger.debug("第一阶段完成,进入第二阶段：下载")

            # 第二阶段：下载（yt-dlp 自动管理文件名和临时目录）
            task.status = "downloading"

            temp_file = await self._do_download(task.url, task, progress_callback)
            logger.debug("第二阶段返回 - temp_file: %s", temp_file)
            
            if not temp_file:
                task.status = "failed"
                task.error = "未找到下载的临时文件"
                logger.error("第二阶段失败: temp_file 为 None")
                await progress_callback(task)
                return

            self._enforce_final_size_limit(temp_file)
            await progress_callback(task)

            # 第三阶段：后处理
            logger.debug("进入第三阶段：后处理, temp_file: %s", temp_file)
            with suppress(FileExistsError):
                await self._post_process(temp_file, task)

            # 检查后处理阶段是否设置了错误（如文件完整性问题）
            if task.error:
                task.status = "failed"
                task.completed_at = datetime.now(UTC)
                logger.error("后处理检测到文件问题: %s", task.error)
                await progress_callback(task)
                return

            task.status = "completed"
            task.progress = 100.0
            task.completed_at = datetime.now(UTC)
            logger.debug("========================================")
            logger.debug("下载任务完成! task_id: %s, status: %s", task.task_id, task.status)
            logger.debug("最终文件: %s", task.filepath)
            logger.debug("========================================")
            # 使缓存失效
            self.invalidate_file_index_cache()
            self.invalidate_hash_index()
            await progress_callback(task)

        except DownloadCancelledError as e:
            task.status = "cancelled"
            task.error = str(e) or "下载已取消"
            task.completed_at = datetime.now(UTC)
            logger.info("下载已取消: task_id=%s, reason=%s", task.task_id, task.error)
            self.cleanup_download_artifacts(task, temp_file=temp_file)
            self.cleanup_temp_files(task.task_id)
            await progress_callback(task)

        except Exception as e:
            task.status = "failed"
            task.error = self._format_error_message(e)
            task.completed_at = datetime.now(UTC)
            logger.error("========================================")
            logger.error("下载失败! task_id: %s", task.task_id)
            logger.error("异常类型: %s", type(e).__name__)
            logger.error("异常信息: %s", e)
            import traceback
            logger.error("堆栈跟踪:\n%s", traceback.format_exc())
            logger.error("========================================")
            # 清理残留临时文件，避免重试时冲突
            self.cleanup_download_artifacts(task, temp_file=temp_file)
            self.cleanup_temp_files(task.task_id)
            await progress_callback(task)

    def _format_error_message(self, error: Exception) -> str:
        """
        格式化 yt-dlp 错误信息，返回用户友好的提示。

        Args:
            error: 捕获的异常对象。

        Returns:
            用户友好的错误提示。
        """
        error_str = str(error)

        if isinstance(error, DownloadSizeLimitError):
            return error_str

        # 视频内容相关
        if "No video could be found" in error_str or "No videos found" in error_str:
            return "该链接没有视频文件"

        if "Private video" in error_str or "This video is private" in error_str:
            return "没有访问权限"

        if "Sign in to confirm" in error_str or "Login" in error_str or "authentication" in error_str.lower():
            return "没有访问权限"

        if "Video unavailable" in error_str or "This video is not available" in error_str:
            return "视频不存在"

        if "Blocked" in error_str and "country" in error_str.lower():
            return "该视频在您的地区不可用"

        # 播放列表/多视频检测
        if isinstance(error, ValueError) and ("播放列表" in error_str or "多视频" in error_str):
            return error_str

        if isinstance(error, ValueError) and "视频文件超过大小限制" in error_str:
            return error_str

        # URL/网站支持
        if "Unsupported URL" in error_str or "No supported URL" in error_str:
            return "不支持的视频链接"

        # HTTP 状态码
        if ("BiliBili" in error_str or "bilibili" in error_str.lower()) and "412" in error_str:
            return "B 站访问被拦截（HTTP 412），请更新完整 Cookie 后重试"

        if "404" in error_str:
            return "视频不存在"

        if "403" in error_str:
            return "没有访问权限"

        if "HTTP Error" in error_str:
            return "无法访问该链接"

        # 网络相关
        if "Connection" in error_str and ("refused" in error_str.lower() or "reset" in error_str.lower()):
            return "网络连接失败"

        if "timed out" in error_str.lower() or "timeout" in error_str.lower():
            return "下载超时"

        if "fragment" in error_str.lower() and ("failed" in error_str.lower() or "error" in error_str.lower()):
            return "视频片段下载失败"

        if "Unable to download video data" in error_str:
            return "无法下载视频数据"

        if "Unable to download webpage" in error_str:
            return "无法访问该网页"

        # ffmpeg 相关
        if ("ffmpeg" in error_str.lower() or "ffprobe" in error_str.lower()) and ("not found" in error_str.lower() or "not installed" in error_str.lower()):
            return "系统未安装 ffmpeg"

        if "merge" in error_str.lower() and ("failed" in error_str.lower() or "error" in error_str.lower()):
            return "视频合并失败"

        # 默认返回简洁提示
        return "下载失败，请检查链接后重试"
