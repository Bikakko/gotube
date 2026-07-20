"""
GoTube 数据库定时备份

应用内后台任务：每隔 N 小时用 VACUUM INTO 对 gotube.db 做一次在线一致快照，
只保留最近 N 份。单 Worker 部署下不会出现多进程重复备份。

VACUUM INTO 是 SQLite 的在线备份机制——服务无需停机，不会拷到写一半的损坏文件，
也不会漏掉 WAL 日志里尚未合并进主库的数据。
"""

import asyncio
import logging
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from .config import settings

logger = logging.getLogger(__name__)

BACKUP_PREFIX = "gotube_"
BACKUP_SUFFIX = ".db"


def perform_backup() -> Path | None:
    """执行一次数据库备份并轮转，返回新备份文件路径；失败返回 None。"""
    backup_dir = settings.backup_dir
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = backup_dir / f"{BACKUP_PREFIX}{timestamp}{BACKUP_SUFFIX}"

        # 用独立 sqlite3 连接执行 VACUUM INTO，绕开 SQLAlchemy 会话的事务限制；
        # isolation_level=None 即 autocommit，因为 VACUUM 不能在事务中执行。
        conn = sqlite3.connect(str(settings.db_file))
        try:
            conn.isolation_level = None
            conn.execute("VACUUM INTO ?", (str(target),))
        finally:
            conn.close()

        kept = _rotate(backup_dir, settings.backup_retention)
        size_kb = target.stat().st_size / 1024
        logger.info("数据库备份完成: %s (%.1f KB)，当前保留 %d 份", target.name, size_kb, kept)
        return target
    except Exception as e:
        logger.warning("数据库备份失败: %s", e)
        return None


def _rotate(backup_dir: Path, keep: int) -> int:
    """按文件名（即时间戳）排序，只保留最新 keep 份，返回保留份数。"""
    files = sorted(backup_dir.glob(f"{BACKUP_PREFIX}*{BACKUP_SUFFIX}"))
    for old in files[:-keep]:
        try:
            old.unlink()
        except OSError as e:
            logger.warning("删除旧备份失败 %s: %s", old.name, e)
    return min(len(files), keep)


def _backup_due(interval_seconds: float) -> bool:
    """距离上一份备份是否已超过间隔（或尚无任何备份）。

    以此判断而非"每次启动都备份"，可避免服务频繁重启时反复备份、
    把保留的几份都挤在同一天，从而保证"每 N 小时一份"的覆盖节奏。
    """
    backup_dir = settings.backup_dir
    files = sorted(backup_dir.glob(f"{BACKUP_PREFIX}*{BACKUP_SUFFIX}")) if backup_dir.exists() else []
    if not files:
        return True
    age_seconds = time.time() - files[-1].stat().st_mtime
    return age_seconds >= interval_seconds


async def backup_loop() -> None:
    """后台循环：到点就备份，然后休眠一个间隔。异常不中断循环。"""
    interval_seconds = settings.backup_interval_hours * 3600
    logger.info(
        "数据库定时备份已启动：每 %d 小时一次，保留 %d 份，目录 %s",
        settings.backup_interval_hours, settings.backup_retention, settings.backup_dir,
    )
    while True:
        try:
            if _backup_due(interval_seconds):
                await asyncio.to_thread(perform_backup)
        except Exception as e:
            logger.warning("数据库备份任务异常: %s", e)
        await asyncio.sleep(interval_seconds)
