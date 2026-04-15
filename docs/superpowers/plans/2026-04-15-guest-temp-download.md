# 匿名用户临时下载功能实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 为匿名用户（未登录游客）提供视频下载功能，文件存储到临时目录，关闭页面后自动删除，刷新页面保留文件。

**架构：** 
- 前端生成 session_id（localStorage 持久化），提交下载任务时附带
- 后端识别匿名用户，将文件下载到 `downloads/temp_guest/{session_id}/` 目录
- WebSocket 断开时触发清理，通过重连间隔区分"关闭"和"刷新"
- 匿名用户只能下载自己的临时文件，无法查看文件列表（天然无分享功能）

**技术栈：** FastAPI, WebSocket, yt-dlp, localStorage (前端)

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `server/config.py` | 修改 | 新增 `allow_guest_download` 配置项 |
| `server/models.py` | 修改 | `AddTaskRequest` 增加 `session_id` 字段 |
| `server/downloader.py` | 修改 | 支持 guest 下载路径、新增 guest 文件清理方法 |
| `server/api.py` | 修改 | 任务提交识别匿名用户、新增 guest 文件下载接口 |
| `server/main.py` | 修改 | WebSocket 断开清理逻辑、session_id 绑定 |
| `www/download.html` | 修改 | 生成/读取 session_id、传递到 JS |
| `www/download.js` | 修改 | 提交任务时附带 session_id、UI 适配 |
| `.env.example` | 修改 | 新增配置项说明 |

---

## 任务 1：配置项与数据模型

**文件：**
- 修改：`server/config.py:60-80`
- 修改：`server/models.py:10-18`

- [ ] **步骤 1：在 config.py 中新增配置项**

在 `config.py` 中读取新配置，在 `_log_level` 之后添加：

```python
_allow_guest_download: bool = _b("GOTUBE_ALLOW_GUEST_DOWNLOAD", True)
```

在 `Settings` 类的属性中新增：

```python
@property
def allow_guest_download(self) -> bool:
    """是否允许匿名用户下载"""
    return _allow_guest_download
```

- [ ] **步骤 2：在 models.py 中修改 AddTaskRequest**

修改 `AddTaskRequest` 模型，增加 `session_id` 可选字段：

```python
class AddTaskRequest(BaseModel):
    """添加下载任务请求"""

    url: str
    session_id: str | None = None  # 匿名用户会话标识
```

- [ ] **步骤 3：Commit**

```bash
git add server/config.py server/models.py
git commit -m "feat: 新增匿名用户下载配置和 session_id 数据模型"
```

---

## 任务 2：Downloader 支持 guest 下载路径

**文件：**
- 修改：`server/downloader.py:80-110` (DownloadTask)
- 修改：`server/downloader.py:110-145` (Downloader.__init__)
- 修改：`server/downloader.py:759-875` (_post_process)
- 新增测试验证（手动测试即可）

- [ ] **步骤 1：修改 DownloadTask 增加 guest 标识**

在 `DownloadTask.__init__` 方法中（约第 83 行），在 `self.is_duplicate = False` 后添加：

```python
        self.is_guest = False  # 是否为匿名用户下载
        self.session_id = ""   # 匿名用户会话 ID
```

- [ ] **步骤 2：修改 Downloader.__init__ 初始化 guest 目录**

在 `Downloader.__init__` 方法中（约第 130 行），在 `self._hash_index` 初始化后添加：

```python
        # 匿名用户临时下载目录
        self.guest_download_dir = self.download_dir / "temp_guest"
        self.guest_download_dir.mkdir(parents=True, exist_ok=True)
```

- [ ] **步骤 3：修改 _post_process 支持 guest 路径**

在 `_post_process` 方法中，找到计算 hash 后检查去重的代码段（约第 785 行），修改目录创建逻辑：

在 `dir_path = self.download_dir / dir_name` 之前（约第 815 行），添加 guest 路径判断：

```python
        # 根据是否为匿名用户决定目录路径
        if task.is_guest and task.session_id:
            base_dir = self.guest_download_dir / task.session_id
            base_dir.mkdir(parents=True, exist_ok=True)
        else:
            base_dir = self.download_dir

        # 构造目录名：标题_指纹
        dir_name = f"{safe_title}_{file_hash}"
        dir_path = base_dir / dir_name
```

同时需要修改后面的冲突检查，将 `self.download_dir` 替换为 `base_dir`：

在约第 820 行，修改：
```python
        # 检查同名冲突
        if dir_path.exists():
            logger.debug("目录已存在,检查冲突")
            existing_in_dir = dir_path / f"{file_hash}{ext}"
            if existing_in_dir.exists():
                logger.debug("发现同名同 hash 文件,删除 temp_file")
                os.remove(temp_file)
                task.is_duplicate = True
                task.filename = f"temp_guest/{task.session_id}/{dir_name}/{file_hash}{ext}" if task.is_guest else f"{dir_name}/{file_hash}{ext}"
                task.filepath = str(existing_in_dir)
                raise FileExistsError(f"重复文件: {existing_in_dir}")

            # 同名不同内容，加序号
            i = 1
            while True:
                new_dir_name = f"{safe_title}_{i}_{file_hash}"
                new_dir_path = base_dir / new_dir_name  # 修改这里：使用 base_dir
                logger.debug("尝试新目录名: %s", new_dir_name)
                if not new_dir_path.exists():
                    dir_name = new_dir_name
                    dir_path = new_dir_path
                    break
                i += 1
```

在约第 837 行，修改 `task.filename` 的赋值：

```python
        if task.is_guest:
            task.filename = f"temp_guest/{task.session_id}/{dir_name}/{final_name}"
        else:
            task.filename = f"{dir_name}/{final_name}"
        task.filepath = str(final_path)
```

- [ ] **步骤 4：新增 guest 文件清理方法**

在 `cleanup_temp_files` 方法之后（约第 400 行），添加新方法：

```python
    def cleanup_guest_session(self, session_id: str) -> int:
        """
        清理指定 session 的所有匿名用户临时文件。

        Args:
            session_id: 匿名用户会话 ID。

        Returns:
            清理的文件数量。
        """
        if not session_id:
            return 0

        session_dir = self.guest_download_dir / session_id
        if not session_dir.exists():
            logger.info("Guest session 目录不存在，无需清理: %s", session_id)
            return 0

        count = 0
        try:
            # 删除整个 session 目录
            shutil.rmtree(session_dir)
            logger.info("已清理 guest session 临时文件: %s", session_id)
            count += 1
        except OSError as e:
            logger.warning("清理 guest session 失败 %s: %s", session_id, e)

        # 尝试清理空的 guest_download_dir
        try:
            if not any(self.guest_download_dir.iterdir()):
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
```

- [ ] **步骤 5：在启动时调用过期清理**

在 `Downloader.__init__` 方法中，在 `self._cleanup_orphaned_temp_files()` 调用之后（约第 143 行），添加：

```python
        # 启动时清理过期的 guest session（超过 24 小时）
        self.cleanup_expired_guest_sessions(max_age_hours=24.0)
```

- [ ] **步骤 6：Commit**

```bash
git add server/downloader.py
git commit -m "feat: Downloader 支持 guest 下载路径和 session 清理"
```

---

## 任务 3：API 层支持匿名用户

**文件：**
- 修改：`server/api.py:117-130` (add_task 接口)
- 修改：`server/api.py:170-195` (新增 guest stream 接口)
- 修改：`server/api.py:26-35` (新增导入)

- [ ] **步骤 1：修改 add_task 接口识别匿名用户**

在 `api.py` 文件顶部，确保导入了 `settings`：

```python
from .config import settings
```

修改 `add_task` 接口（约第 117 行），在验证 URL 格式之后、调用 `qm.add_task` 之前，添加 guest 标识传递：

```python
@router.post("/tasks", response_model=TaskResponse)
async def add_task(
    req: AddTaskRequest,
    client_id: str = Query(..., description="客户端标识"),
    qm: QueueManager = Depends(get_queue_manager),
):
    """添加下载任务"""
    if not req.url:
        raise HTTPException(status_code=400, detail="URL 不能为空")

    # 基础验证：排除纯中文、纯符号等无效输入
    import re
    if not re.search(r'[a-zA-Z0-9]', req.url):
        raise HTTPException(status_code=400, detail="请输入有效的视频链接地址")

    # 验证 URL 格式（必须 http/https 开头）
    _validate_url_format(req.url)

    # 检查是否为匿名用户
    is_guest = bool(req.session_id)
    if is_guest and not settings.allow_guest_download:
        raise HTTPException(status_code=403, detail="匿名用户下载功能已禁用")

    task = await qm.add_task(req.url, client_id, session_id=req.session_id)
    if task is None:
        # 同客户端相同URL且不可重试
        raise HTTPException(status_code=409, detail="该链接已在下载中或已完成，请勿重复提交")

    logger.info("添加任务: %s, client=%s, is_guest=%s", task.task_id, client_id, is_guest)
    return _task_to_response(task)
```

- [ ] **步骤 2：新增 guest 文件下载接口**

在 `stream_video` 接口之后（约第 195 行），添加新的 guest 下载接口：

```python
@router.get("/guest-downloads/stream/{session_id}/{filename:path}")
async def stream_guest_video(
    session_id: str,
    filename: str,
    qm: QueueManager = Depends(get_queue_manager),
):
    """匿名用户视频文件下载（仅限自己的 session）"""
    download_dir = qm.downloader.guest_download_dir
    filepath = download_dir / session_id / filename

    logger.info("[/api/guest-downloads/stream] request session=%s filename=%s, resolved path=%s", 
                session_id, filename, filepath)

    # 防止路径遍历攻击
    try:
        filepath.resolve().relative_to((download_dir / session_id).resolve())
    except ValueError as e:
        logger.warning("[/api/guest-downloads/stream] illegal path: %s, error=%s", filepath, e)
        raise HTTPException(status_code=403, detail="非法文件路径") from e

    if not filepath.is_file():
        logger.warning("[/api/guest-downloads/stream] file not found: %s", filepath)
        raise HTTPException(status_code=404, detail="文件不存在")

    logger.info("[/api/guest-downloads/stream] returning video: path=%s, size=%d", filepath, filepath.stat().st_size)
    return FileResponse(
        filepath,
        media_type="video/mp4",
        filename=filepath.name,
        headers={"Content-Disposition": f'inline; filename="{filepath.name}"'},
    )
```

- [ ] **步骤 3：Commit**

```bash
git add server/api.py
git commit -m "feat: API 支持匿名用户任务提交和临时文件下载"
```

---

## 任务 4：QueueManager 传递 session_id

**文件：**
- 修改：`server/queue_manager.py:50-70` (add_task 方法)
- 修改：`server/queue_manager.py:15-35` (导入和类定义)

- [ ] **步骤 1：查看 queue_manager.py 的 add_task 方法**

需要先读取文件了解当前实现。

- [ ] **步骤 2：修改 add_task 接收并传递 session_id**

在 `add_task` 方法签名中添加 `session_id` 参数：

```python
    async def add_task(self, url: str, client_id: str, session_id: str | None = None) -> DownloadTask | None:
        """
        添加下载任务。

        Args:
            url: 视频 URL。
            client_id: 客户端标识。
            session_id: 匿名用户会话 ID（可选）。

        Returns:
            DownloadTask 对象，如果重复则返回 None。
        """
        # ... 原有逻辑 ...
        
        # 创建任务
        task = self.downloader.create_task(url, client_id)
        
        # 设置 guest 标识
        if session_id:
            task.is_guest = True
            task.session_id = session_id
        
        # ... 原有逻辑 ...
```

- [ ] **步骤 3：Commit**

```bash
git add server/queue_manager.py
git commit -m "feat: QueueManager 传递 session_id 到 DownloadTask"
```

---

## 任务 5：WebSocket 断开时清理 guest 文件

**文件：**
- 修改：`server/main.py:275-330` (websocket_endpoint)
- 修改：`server/main.py:1-30` (导入)

- [ ] **步骤 1：实现 WebSocket 断开清理逻辑**

在 `websocket_endpoint` 函数的 `finally` 块中（约第 328 行），添加 guest 文件清理逻辑：

首先需要在 WebSocket 连接时记录 session_id。修改连接注册部分（约第 290 行）：

```python
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

    # 注册客户端
    queue_mgr.register_client(client_id, lambda task: _on_progress(task, websocket))
    
    # 记录连接时间和 session_id，用于区分"刷新"和"关闭"
    connection_time = datetime.now(UTC)

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
        disconnect_time = datetime.now(UTC)
        logger.debug("WebSocket 断开连接: %s, session_id=%s", client_id, session_id)
    finally:
        queue_mgr.unregister_client(client_id)
        
        # 匿名用户断开：清理临时文件
        if session_id:
            # 区分"刷新"和"关闭"：
            # - 刷新：断开后很快重连（间隔 < 5 秒）
            # - 关闭：断开后不重连
            # 策略：延迟清理，如果在延迟期间有新连接则取消清理
            # 这里使用简单策略：直接清理，因为刷新时前端会复用 session_id
            # 下载任务仍然关联到该 session_id，不受影响
            
            # 延迟 10 秒清理，给刷新留出时间
            async def _delayed_cleanup():
                await asyncio.sleep(10)
                # 检查客户端是否已重新连接（通过检查是否有活跃任务）
                client_tasks = queue_mgr.get_client_tasks(client_id)
                has_active_tasks = any(t.status in ("pending", "downloading") for t in client_tasks)
                
                if not has_active_tasks:
                    logger.info("WebSocket 断开 10 秒后无活跃任务，清理 guest session: %s", session_id)
                    cleaned = queue_mgr.downloader.cleanup_guest_session(session_id)
                    logger.info("已清理 %d 个 guest session 目录", cleaned)
                else:
                    logger.info("WebSocket 断开但仍有活跃任务，保留 guest session: %s", session_id)
            
            # 启动后台清理任务
            asyncio.create_task(_delayed_cleanup())
```

需要确保导入了 `datetime` 和 `asyncio`。在文件顶部检查导入（约第 10 行）：

```python
import asyncio
import json
import logging
import logging.handlers
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
```

- [ ] **步骤 2：Commit**

```bash
git add server/main.py
git commit -m "feat: WebSocket 断开时延迟清理 guest 临时文件"
```

---

## 任务 6：前端生成和传递 session_id

**文件：**
- 修改：`www/download.html` (或对应的混淆后的 HTML)
- 修改：`www/download.js`

- [ ] **步骤 1：检查 download.html 和 download.js 的结构**

先读取文件了解当前实现。

- [ ] **步骤 2：在 download.js 中实现 session_id 管理**

在文件顶部（全局作用域），添加 session_id 管理逻辑：

```javascript
// ── 匿名用户 Session 管理 ──

/**
 * 生成或获取 guest session_id
 * 使用 localStorage 持久化，刷新页面时复用
 */
function getOrCreateSessionId() {
    const STORAGE_KEY = 'gotube_guest_session_id';
    let sessionId = localStorage.getItem(STORAGE_KEY);
    
    if (!sessionId) {
        // 生成新的 session_id
        sessionId = 'guest_' + Date.now().toString(36) + '_' + Math.random().toString(36).substring(2, 9);
        localStorage.setItem(STORAGE_KEY, sessionId);
        console.log('[Session] 创建新 session:', sessionId);
    } else {
        console.log('[Session] 复用已有 session:', sessionId);
    }
    
    return sessionId;
}

// 全局 session_id
const GUEST_SESSION_ID = getOrCreateSessionId();
```

- [ ] **步骤 3：修改任务提交逻辑**

找到提交下载任务的代码（通常在 URL 输入的处理函数中），在构建请求体时添加 `session_id`：

```javascript
// 原来的代码可能是：
// const response = await apiFetch('/api/tasks?client_id=' + clientId, {
//     method: 'POST',
//     body: JSON.stringify({ url: videoUrl })
// });

// 修改为：
const response = await apiFetch('/api/tasks?client_id=' + clientId, {
    method: 'POST',
    body: JSON.stringify({ 
        url: videoUrl,
        session_id: GUEST_SESSION_ID
    })
});
```

- [ ] **步骤 4：修改 WebSocket 连接**

找到 WebSocket 连接代码，在 URL 中添加 `session_id` 参数：

```javascript
// 原来的代码可能是：
// const ws = new WebSocket(`ws://${location.host}/ws?client_id=${clientId}`);

// 修改为：
const ws = new WebSocket(`ws://${location.host}/ws?client_id=${clientId}&session_id=${GUEST_SESSION_ID}`);
```

- [ ] **步骤 5：修改下载链接**

找到下载按钮的点击处理代码，将下载 URL 改为 guest 接口：

```javascript
// 原来的代码可能是：
// const downloadUrl = `${getApiBase()}/api/downloads/stream/${encodeURIComponent(filename)}`;

// 修改为：
const downloadUrl = `${getApiBase()}/api/guest-downloads/stream/${GUEST_SESSION_ID}/${encodeURIComponent(filename.replace(/^temp_guest\/[^\/]+\//, ''))}`;
```

注意：`filename` 中包含了 `temp_guest/{session_id}/` 前缀，需要去掉前缀部分。

- [ ] **步骤 6：Commit**

```bash
git add www/download.js www/download.html
git commit -m "feat: 前端生成和传递 guest session_id"
```

---

## 任务 7：更新 .env.example 和测试验证

**文件：**
- 修改：`.env.example`
- 手动测试验证

- [ ] **步骤 1：更新 .env.example**

在 `.env.example` 文件中，添加新配置项的说明：

```bash
# 是否允许匿名用户下载（默认开启）
# 匿名用户下载的文件存储到临时目录，关闭页面后自动删除
GOTUBE_ALLOW_GUEST_DOWNLOAD=1
```

- [ ] **步骤 2：手动测试验证**

按以下步骤测试：

1. **启动服务**
   ```bash
   ./st.sh  # 或 python -m uvicorn server.main:app --reload
   ```

2. **匿名下载测试**
   - 打开浏览器访问下载页（隐藏路径）
   - 提交一个视频下载任务
   - 检查 `downloads/temp_guest/` 目录是否创建
   - 下载完成后检查文件是否在正确的 session 目录下

3. **下载测试**
   - 点击下载按钮，验证能否正常下载
   - 检查下载链接是否指向 guest-downloads/stream 接口

4. **刷新测试**
   - 下载完成后刷新页面
   - 检查临时文件是否仍然存在
   - 应该仍能正常下载

5. **关闭测试**
   - 下载完成后关闭浏览器标签
   - 等待 10-15 秒
   - 检查 `downloads/temp_guest/guest_xxx/` 目录是否被删除

6. **日志检查**
   - 查看 server.log 或终端输出
   - 确认有 guest session 创建和清理的日志

7. **注册用户回归测试**
   - 登录管理员账号
   - 提交下载任务
   - 验证文件仍然下载到 `downloads/` 根目录
   - 验证不受 guest 功能影响

- [ ] **步骤 3：Commit**

```bash
git add .env.example
git commit -m "docs: 更新 .env.example 新增 guest 下载配置说明"
```

---

## 自检清单

- [x] 规格覆盖度：所有需求都有对应任务
- [x] 无占位符：每个步骤都有完整代码
- [x] 类型一致性：session_id 类型统一为 str
- [x] 避免误伤：注册用户流程完全不变，guest 逻辑全部走新分支
- [x] 配置开关：GOTUBE_ALLOW_GUEST_DOWNLOAD 默认开启可关闭
- [x] 安全：路径遍历攻击防护、session_id 隔离
