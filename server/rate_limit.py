"""内存速率限制组件。

包含两个独立的限制器：
- LoginThrottle: 登录失败计数，窗口内失败达到阈值后锁定一段时间，
  防止针对登录接口的暴力破解；
- SlidingWindowLimiter: 按客户端 IP 的滑动窗口速率限制，
  用于全局 API 层面的请求频率控制。

说明：均为单实例进程内实现，与反向代理限流互为补充（防御纵深）。
"""

import threading
import time
from collections import deque

from fastapi import HTTPException


def get_client_ip(request) -> str:
    """提取客户端 IP：优先 X-Forwarded-For 首跳（反向代理场景），否则取连接地址。"""
    forwarded = request.headers.get("x-forwarded-for", "")
    for part in forwarded.split(","):
        candidate = part.strip()
        if candidate:
            return candidate
    client = getattr(request, "client", None)
    return client.host if client else "unknown"


class LoginThrottle:
    """登录失败锁定：窗口内失败达到阈值即锁定，锁定期间拒绝一切尝试。"""

    _KEY_MAX_LEN = 128

    def __init__(
        self,
        max_failures: int = 5,
        window_seconds: float = 300.0,
        lockout_seconds: float = 900.0,
    ):
        self._max_failures = max_failures
        self._window = window_seconds
        self._lockout = lockout_seconds
        self._failures: dict[str, list[float]] = {}
        self._locked_until: dict[str, float] = {}
        self._lock = threading.Lock()

    def check(self, *keys: str) -> None:
        """若任一 key 处于锁定期，抛出 429。"""
        now = time.monotonic()
        with self._lock:
            for raw_key in keys:
                key = raw_key[: self._KEY_MAX_LEN]
                until = self._locked_until.get(key, 0.0)
                if until > now:
                    raise HTTPException(
                        status_code=429,
                        detail="失败次数过多，已临时锁定，请稍后再试",
                    )
                if until:
                    # 锁定已过期，清理状态
                    del self._locked_until[key]
                    self._failures.pop(key, None)

    def record_failure(self, *keys: str) -> None:
        """记录一次失败；窗口内累计达到阈值则触发锁定。"""
        now = time.monotonic()
        with self._lock:
            for raw_key in keys:
                key = raw_key[: self._KEY_MAX_LEN]
                hits = self._failures.setdefault(key, [])
                hits[:] = [t for t in hits if now - t <= self._window]
                hits.append(now)
                if len(hits) >= self._max_failures:
                    self._locked_until[key] = now + self._lockout
                    hits.clear()

    def clear(self, *keys: str) -> None:
        """登录成功后清除对应 key 的失败计数与锁定。"""
        with self._lock:
            for raw_key in keys:
                key = raw_key[: self._KEY_MAX_LEN]
                self._failures.pop(key, None)
                self._locked_until.pop(key, None)


class SlidingWindowLimiter:
    """按 key（通常为客户端 IP）的滑动窗口限流器。"""

    _PRUNE_INTERVAL_SECONDS = 60.0

    def __init__(self, max_requests: int, window_seconds: float = 60.0):
        self._max_requests = max_requests
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._last_prune = 0.0

    def allow(self, key: str) -> bool:
        """窗口内未超限则记账并放行，否则拒绝。"""
        now = time.monotonic()
        with self._lock:
            self._maybe_prune(now)
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] > self._window:
                hits.popleft()
            if len(hits) >= self._max_requests:
                return False
            hits.append(now)
            return True

    def _maybe_prune(self, now: float) -> None:
        """定期清理长时间无请求的 key，防止字典无限增长。"""
        if now - self._last_prune < self._PRUNE_INTERVAL_SECONDS:
            return
        self._last_prune = now
        idle_keys = [
            k for k, q in self._hits.items()
            if not q or now - q[-1] > self._window
        ]
        for k in idle_keys:
            del self._hits[k]
