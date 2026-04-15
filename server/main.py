"""
GoTube FastAPI 服务入口

负责应用初始化、生命周期管理、页面路由和 WebSocket 连接。
"""

import asyncio
import json
import logging
import logging.handlers
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .api import get_queue_manager
from .api import router as api_router
from .admin_api import router as admin_api_router
from .config import settings
from .db import init_db, get_session, sync_admins_from_env
from .downloader import VIDEO_EXTENSIONS, Downloader, DownloadTask
from .queue_manager import QueueManager

logger = logging.getLogger(__name__)

# 项目路径
PROJECT_ROOT = settings.project_root
WWW_DIR = PROJECT_ROOT / settings.www_dir
LOG_FILE = PROJECT_ROOT / "server.log"

# 配置根日志级别（从 .env 读取）
log_level = getattr(logging, settings.log_level, logging.ERROR)
logging.getLogger().setLevel(log_level)

# 控制台日志处理器（实时输出到终端）
_ch = logging.StreamHandler()
_ch.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
)
_ch.setLevel(log_level)
logging.getLogger().addHandler(_ch)

# 文件日志处理器（RotatingFileHandler，只记录 ERROR 级别，最大 5MB，保留 5 个备份）
_fh = logging.handlers.RotatingFileHandler(
    LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
)
_fh.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
)
_fh.setLevel(logging.ERROR)
logging.getLogger().addHandler(_fh)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 初始化数据库
    init_db(str(settings.db_file))
    
    # 确保存在默认管理员
    with get_session() as session:
        sync_admins_from_env(session, settings.admins)

    downloader = Downloader()
    queue_mgr = QueueManager(downloader, max_concurrent=settings.max_concurrent)

    # 挂载到 app state
    app.state.downloader = downloader
    app.state.queue_manager = queue_mgr

    logger.info("GoTube 启动，下载目录: %s", downloader.download_dir)
    logger.info("最大并发下载数: %d", settings.max_concurrent)

    yield

    # 关闭阶段
    logger.info("GoTube 正在关闭...")
    try:
        await queue_mgr.shutdown()
    except Exception as e:
        logger.warning("QueueManager 关闭异常: %s", e)
    logger.info("GoTube 已关闭")


app = FastAPI(
    title="GoTube",
    description="自托管多平台视频下载工具",
    version="3.0.4",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)

# CORS 中间件（明确来源，不使用 * + credentials）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载 API 路由器
app.include_router(api_router, prefix="/api")

# 挂载管理页面 API 路由器
app.include_router(admin_api_router, prefix=f"/{settings.hidden_path}/admin/api")


# ── 辅助函数 ──


def _serve_html(filename: str) -> HTMLResponse:
    """读取并返回 HTML 内容，支持简单的模板变量替换"""
    filepath = WWW_DIR / filename
    if not filepath.exists():
        logger.error("HTML 文件不存在: %s", filepath)
        return HTMLResponse("<h1>404 Not Found</h1>", status_code=404)
    
    try:
        content = filepath.read_text(encoding="utf-8")
        # 注入配置变量，供前端 JS 使用
        content = content.replace("{{HIDDEN_PATH}}", settings.hidden_path)
        return HTMLResponse(content)
    except Exception as e:
        logger.error("读取 HTML 失败: %s, 错误: %s", filepath, e)
        return HTMLResponse("<h1>500 Internal Server Error</h1>", status_code=500)


def _get_queue_manager() -> QueueManager:
    """从 app state 获取 queue_manager"""
    return app.state.queue_manager


# ── 静态文件服务 ──


if WWW_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WWW_DIR)), name="static")


# ── 页面路由 ──


@app.get("/", response_model=None)
async def root_page() -> FileResponse | HTMLResponse:
    """根路径 - 空白页（v.pikakko.top）"""
    return _serve_html("index.html")


@app.get(f"/{settings.hidden_path}", response_model=None)
async def download_page() -> FileResponse | HTMLResponse:
    """下载页（隐藏路径，只有知道地址的人才能访问）"""
    return _serve_html("download.html")


@app.get(f"/{settings.hidden_path}/", response_model=None)
async def download_page_trailing_slash() -> RedirectResponse:
    """下载页带尾斜杠，重定向到不带斜杠的版本"""
    return RedirectResponse(url=f"/{settings.hidden_path}", status_code=301)


@app.get(f"/{settings.hidden_path}/admin", response_model=None)
async def admin_page() -> FileResponse | HTMLResponse:
    """管理页面入口"""
    return _serve_html("admin/admin.html")


@app.get("/watch.html", response_model=None)
async def watch() -> FileResponse | HTMLResponse:
    """精简播放页（分享链接用，不暴露主站）"""
    return _serve_html("watch.html")


@app.get("/watch", response_model=None)
async def watch_unified(
    request: Request,
    v: str | None = Query(None),
) -> FileResponse | HTMLResponse:
    """
    统一播放端点（/watch?v={hash_id}）。

    根据 Accept 请求头智能判断：
    - text/html  → 返回播放页面
    - video/*    → 返回视频流
    """
    accept = request.headers.get("Accept", "")
    logger.info("[/watch] request: v=%s, accept=%s, headers=%s", v, accept, dict(request.headers))

    if "text/html" in accept:
        logger.info("[/watch] returning HTML page")
        return _serve_html("watch.html")

    # 视频请求：根据 hash_id 查找文件并返回视频流
    if v:
        qm: QueueManager = get_queue_manager(request)
        download_dir = qm.downloader.download_dir

        # 使用 hash 索引查找
        hash_index = qm.downloader._build_hash_index()
        logger.info("[/watch] hash_index keys: %s", list(hash_index.keys())[:10])
        matched_file: Path | None = None
        for h, fp in hash_index.items():
            if h.startswith(v) or v.startswith(h):
                matched_file = fp
                logger.info("[/watch] matched via hash index: h=%s, fp=%s", h, fp)
                break

        if matched_file is None:
            for f in download_dir.rglob(f"{v}*"):
                if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS:
                    matched_file = f
                    logger.info("[/watch] matched via rglob: %s", f)
                    break

        if matched_file is not None and matched_file.is_file():
            logger.info("[/watch] returning video: path=%s, size=%d", matched_file, matched_file.stat().st_size)
            return FileResponse(
                matched_file,
                media_type="video/mp4",
                headers={"Content-Disposition": f'inline; filename="{matched_file.name}"'},
            )
        else:
            logger.warning("[/watch] file not found: v=%s, matched=%s", v, matched_file)

    raise HTTPException(status_code=404, detail="视频不存在或缺少参数")


@app.get("/health")
async def health() -> dict:
    """健康检查"""
    qm = _get_queue_manager()
    return {
        "status": "ok",
        "active_downloads": qm.get_active_count(),
        "queued": qm.get_queue_count(),
    }


@app.get("/{filename:path}", response_model=None)
async def catch_all(
    filename: str,
) -> FileResponse | HTMLResponse:
    """
    捕获其他静态文件请求。

    保护敏感页面：直接访问 index.html / admin.html / download.html 返回 watch.html。
    如果是 www 目录中存在的静态文件，直接返回。
    否则返回 watch.html（分享链接进入）。
    """
    # 保护敏感页面
    if filename in ("index.html", "admin.html", "admin/admin.html", "download.html"):
        return _serve_html("watch.html")

    # 从 www 目录提供静态文件
    ext = Path(filename).suffix.lower()
    static_extensions = {
        ".html",
        ".js",
        ".css",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".svg",
        ".ico",
        ".webp",
    }
    if ext in static_extensions:
        filepath = WWW_DIR / filename
        if filepath.exists():
            return FileResponse(filepath)

    return _serve_html("watch.html")


# ── WebSocket ──

# 记录 guest session_id 的最近连接时间，用于区分"刷新"和"关闭"
_guest_connections: dict[str, float] = {}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    WebSocket 端点，用于实时推送下载进度。

    客户端连接后会被注册到 queue_manager，
    之后所有该客户端的任务进度变更都会通过此连接推送。
    匿名用户断开时会清理临时文件。
    """
    await websocket.accept()

    client_id = websocket.query_params.get("client_id", str(uuid.uuid4())[:8])
    session_id = websocket.query_params.get("session_id", "")  # 获取 session_id
    queue_mgr = _get_queue_manager()

    # 记录 guest 连接时间
    if session_id:
        import time
        _guest_connections[session_id] = time.monotonic()

    # 注册客户端
    queue_mgr.register_client(client_id, lambda task: _on_progress(task, websocket))

    # 发送连接确认
    await websocket.send_json(
        {
            "type": "connected",
            "client_id": client_id,
        }
    )

    # 推送当前客户端所有任务的最新状态
    try:
        client_tasks = queue_mgr.get_client_tasks(client_id)
        for task in client_tasks:
            await _on_progress(task, websocket)
        logger.debug("WebSocket 连接后推送了 %d 个任务状态, client_id=%s", len(client_tasks), client_id)
    except Exception as e:
        logger.warning("推送历史任务状态失败: %s", e)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        logger.debug("WebSocket 断开连接: %s, session_id=%s", client_id, session_id)
    finally:
        queue_mgr.unregister_client(client_id)
        
        # 匿名用户断开：延迟清理临时文件
        if session_id:
            # 区分"刷新"和"关闭"：
            # - 刷新：断开后很快重连（高延迟网络可能需要 10-20 秒）
            # - 关闭：断开后不重连
            # 策略：延迟 30 秒清理，检查 session_id 是否在延迟期间有新连接
            async def _delayed_cleanup():
                import time
                await asyncio.sleep(30)

                # 检查 session_id 是否在 30 秒内有新连接
                last_connect = _guest_connections.get(session_id, 0)
                if time.monotonic() - last_connect < 30:
                    logger.info("session 在延迟期间有新连接，保留 guest session: %s", session_id)
                else:
                    logger.info("session 无新连接，清理 guest session: %s", session_id)
                    cleaned = queue_mgr.downloader.cleanup_guest_session(session_id)
                    logger.info("已清理 %d 个 guest session 目录", cleaned)
                    # 清理连接记录
                    _guest_connections.pop(session_id, None)

            # 启动后台清理任务
            asyncio.create_task(_delayed_cleanup())


async def _on_progress(task: DownloadTask, websocket: WebSocket) -> None:
    """
    下载进度回调，通过 WebSocket 推送。

    Args:
        task: 下载任务对象。
        websocket: WebSocket 连接。
    """
    try:
        data = {
            "type": "progress",
            "task_id": task.task_id,
            "status": task.status,
            "progress": task.progress,
            "speed": task.speed,
            "eta": task.eta,
            "filename": task.filename,
            "title": task.title,
            "file_hash": task.file_hash,
            "error": task.error,
        }
        await websocket.send_json(data)
    except Exception as e:
        logger.debug("on_progress 异常: %s", e)
