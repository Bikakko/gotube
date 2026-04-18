# 下载生命周期与中断机制实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 将下载任务从“页面连接驱动的进度显示”升级为服务端可追踪、可取消、可清理、可恢复的生命周期模型。

**架构：** 下载任务的真实生命周期由服务端 `QueueManager` 和 `Downloader` 管理；WebSocket 只负责进度显示。游客关闭页面后取消下载并清理临时文件；登录用户关闭页面后后台继续下载；登录用户主动退出时由前端让用户选择继续后台下载或取消。

**技术栈：** FastAPI、asyncio、yt-dlp、原生前端 JavaScript、unittest。

---

## 文件结构

- 修改：`server/downloader.py`
  - 扩展 `DownloadTask` 状态和取消字段。
  - 增加 `DownloadCancelledError`。
  - 在 progress hook 中检查取消请求并中断 yt-dlp。
  - 在 `download()` 中单独处理取消并清理残留。
- 修改：`server/queue_manager.py`
  - 保存运行中的 `asyncio.Task` 句柄。
  - 增加按 `task_id`、`client_id`、`session_id`、`owner_user_id` 查询活跃任务的能力。
  - 增加单任务和批量取消接口。
- 修改：`server/api.py`
  - 新增查询活跃任务 API。
  - 新增取消单任务 API。
  - 新增取消当前 client 活跃任务 API。
- 修改：`server/main.py`
  - WebSocket guest session 断开延迟期结束后，先取消该 session 的活跃下载，再清理 guest 目录。
- 修改：`www/download.js`
  - 退出登录前查询活跃任务。
  - 有活跃任务时展示确认选择：继续后台下载并退出，或取消下载并退出。
  - 支持 `cancelled` 状态展示。
- 修改：`www/download.html`
  - 如现有 `confirm()` 不足以表达双选项，则增加轻量退出确认模态框。
- 修改：`tests/test_downloader_transfer_boundaries_unittest.py`
  - 增加下载器取消和残留清理测试。
- 新建：`tests/test_download_cancellation_unittest.py`
  - 覆盖 QueueManager 任务索引、单任务取消、guest session 批量取消、登录用户后台继续下载等服务端生命周期行为。
- 修改：`tests/test_frontend_session_contract_unittest.py`
  - 增加前端退出确认和 `cancelled` 状态契约测试。
- 修改：`docs/superpowers/worklogs/2026-04-18-task-9-download-lifecycle.md`
  - 记录实施过程、验证命令和已知限制。
- 修改：`docs/superpowers/frontend-session-checklist.md`
  - 增加游客关闭、登录用户关闭、退出继续、退出取消等手工检查场景。

---

## 任务 9.1：扩展任务状态模型

**文件：**
- 修改：`server/downloader.py`
- 修改：`www/download.js`
- 测试：`tests/test_downloader_transfer_boundaries_unittest.py`
- 测试：`tests/test_frontend_session_contract_unittest.py`

- [ ] **步骤 1：编写失败测试**

在 `tests/test_downloader_transfer_boundaries_unittest.py` 增加：

```python
def test_task_can_record_cancel_request(self):
    task = DownloadTask("cancel1", "https://example.com/v", "client")

    task.request_cancel("用户取消下载")

    self.assertTrue(task.cancel_requested)
    self.assertEqual(task.cancel_reason, "用户取消下载")
```

在 `tests/test_frontend_session_contract_unittest.py` 增加：

```python
def test_download_page_renders_cancelled_status(self):
    source = read_text("www/download.js")

    self.assertIn("cancelled: '已取消'", source)
    self.assertIn("status-cancelled", source)
```

- [ ] **步骤 2：运行测试确认失败**

运行：

```powershell
venv\Scripts\python.exe -m unittest tests.test_downloader_transfer_boundaries_unittest tests.test_frontend_session_contract_unittest
```

预期：失败，提示 `request_cancel` 不存在，或前端缺少 `cancelled` 状态。

- [ ] **步骤 3：实现最小模型**

在 `DownloadTask.__init__` 增加：

```python
self.cancel_requested = False
self.cancel_reason = ""
```

增加方法：

```python
def request_cancel(self, reason: str = "下载已取消") -> None:
    self.cancel_requested = True
    self.cancel_reason = reason or "下载已取消"
```

在 `www/download.js` 的任务状态 label 中增加：

```javascript
cancelled: '已取消'
```

确认失败任务重试逻辑不匹配 `cancelled`。

- [ ] **步骤 4：运行测试确认通过**

运行：

```powershell
venv\Scripts\python.exe -m unittest tests.test_downloader_transfer_boundaries_unittest tests.test_frontend_session_contract_unittest
```

预期：通过。

- [ ] **步骤 5：提交**

```powershell
git add server/downloader.py www/download.js tests/test_downloader_transfer_boundaries_unittest.py tests/test_frontend_session_contract_unittest.py
git commit -m "feat(下载): 增加任务取消状态"
```

---

## 任务 9.2：QueueManager 保存运行任务索引

**文件：**
- 修改：`server/queue_manager.py`
- 新建：`tests/test_download_cancellation_unittest.py`

- [ ] **步骤 1：编写失败测试**

创建 `tests/test_download_cancellation_unittest.py`，增加：

```python
import asyncio
import tempfile
import unittest
from pathlib import Path

from server.downloader import Downloader
from server.queue_manager import QueueManager


class DownloadCancellationIndexTests(unittest.IsolatedAsyncioTestCase):
    async def test_running_task_is_indexed_by_client_and_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            downloader = Downloader(download_dir=Path(tmp), cookies_file=None)
            qm = QueueManager(downloader, max_concurrent=1)
            started = asyncio.Event()
            release = asyncio.Event()

            async def fake_download(task, callback):
                task.status = "downloading"
                started.set()
                await release.wait()

            downloader.download = fake_download

            task = await qm.add_task("https://example.com/v", "client-a", session_id="guest_abcdefghijklmnop")
            await started.wait()

            self.assertIn(task.task_id, {t.task_id for t in qm.get_active_tasks_for_client("client-a")})
            self.assertIn(task.task_id, {t.task_id for t in qm.get_active_tasks_for_guest_session("guest_abcdefghijklmnop")})

            release.set()
```

- [ ] **步骤 2：运行测试确认失败**

运行：

```powershell
venv\Scripts\python.exe -m unittest tests.test_download_cancellation_unittest
```

预期：失败，提示查询方法不存在。

- [ ] **步骤 3：实现运行索引**

在 `QueueManager.__init__` 增加：

```python
self._running_tasks: dict[str, asyncio.Task] = {}
```

`add_task()` 中保存 create_task 返回值：

```python
runner = asyncio.create_task(self._execute_with_semaphore(task), name=f"download-{task.task_id}")
self._running_tasks[task.task_id] = runner
runner.add_done_callback(lambda _runner, task_id=task.task_id: self._running_tasks.pop(task_id, None))
```

增加查询方法：

```python
def get_active_tasks_for_client(self, client_id: str) -> list[DownloadTask]:
    return [
        task for task in self.downloader.get_tasks_by_client(client_id)
        if task.status in ("pending", "downloading")
    ]

def get_active_tasks_for_guest_session(self, session_id: str) -> list[DownloadTask]:
    return [
        task for task in self.downloader.get_active_tasks()
        if task.is_guest and task.session_id == session_id
    ]

def get_active_tasks_for_owner(self, owner_user_id: int) -> list[DownloadTask]:
    return [
        task for task in self.downloader.get_active_tasks()
        if task.owner_user_id == owner_user_id and not task.is_guest
    ]
```

- [ ] **步骤 4：运行测试确认通过**

运行：

```powershell
venv\Scripts\python.exe -m unittest tests.test_download_cancellation_unittest
```

预期：通过。

- [ ] **步骤 5：提交**

```powershell
git add server/queue_manager.py tests/test_download_cancellation_unittest.py
git commit -m "feat(下载): 跟踪运行中的下载任务"
```

---

## 任务 9.3：下载器支持主动取消与清理

**文件：**
- 修改：`server/downloader.py`
- 测试：`tests/test_downloader_transfer_boundaries_unittest.py`

- [ ] **步骤 1：编写失败测试**

在 `tests/test_downloader_transfer_boundaries_unittest.py` 增加：

```python
def test_progress_hook_raises_when_task_cancel_requested(self):
    with tempfile.TemporaryDirectory() as tmp:
        downloader = Downloader(download_dir=Path(tmp), cookies_file=None)
        task = DownloadTask("cancel2", "https://example.com/v", "client")
        task.request_cancel("用户取消下载")
        hook = downloader._make_progress_hook(task)

        with self.assertRaises(Exception) as ctx:
            hook({"status": "downloading", "downloaded_bytes": 1, "total_bytes": 10})

        self.assertIn("取消", str(ctx.exception))
```

增加异步测试：

```python
async def test_download_marks_cancelled_and_cleans_artifacts(self):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        downloader = Downloader(download_dir=root, cookies_file=None)
        task = DownloadTask("cancel3", "https://example.com/v", "client")
        artifact = root / "Example.mp4.part"
        artifact.write_bytes(b"x")
        task.download_artifact_path = str(artifact)

        async def fake_do_download(url, task, progress_callback):
            task.request_cancel("用户取消下载")
            raise DownloadCancelledError("用户取消下载")

        async def progress_callback(task):
            pass

        downloader._do_download = fake_do_download
        await downloader.download(task, progress_callback)

        self.assertEqual(task.status, "cancelled")
        self.assertFalse(artifact.exists())
```

- [ ] **步骤 2：运行测试确认失败**

运行：

```powershell
venv\Scripts\python.exe -m unittest tests.test_downloader_transfer_boundaries_unittest
```

预期：失败，提示取消异常或处理逻辑不存在。

- [ ] **步骤 3：实现取消异常和下载器处理**

在 `server/downloader.py` 增加：

```python
class DownloadCancelledError(Exception):
    """下载任务被用户或会话生命周期取消。"""
```

在 `_make_progress_hook()` 进入下载分支前检查：

```python
if task.cancel_requested:
    raise DownloadCancelledError(task.cancel_reason or "下载已取消")
```

在 `download()` 的 `except Exception` 前增加：

```python
except DownloadCancelledError as e:
    task.status = "cancelled"
    task.error = str(e) or "下载已取消"
    task.completed_at = datetime.now(UTC)
    self.cleanup_download_artifacts(task, temp_file=temp_file)
    self.cleanup_temp_files(task.task_id)
    await progress_callback(task)
```

保留普通异常处理，不把取消混为失败。

- [ ] **步骤 4：运行测试确认通过**

运行：

```powershell
venv\Scripts\python.exe -m unittest tests.test_downloader_transfer_boundaries_unittest
```

预期：通过。

- [ ] **步骤 5：提交**

```powershell
git add server/downloader.py tests/test_downloader_transfer_boundaries_unittest.py
git commit -m "feat(下载): 支持主动取消和残留清理"
```

---

## 任务 9.4：QueueManager 增加取消入口

**文件：**
- 修改：`server/queue_manager.py`
- 测试：`tests/test_download_cancellation_unittest.py`

- [ ] **步骤 1：编写失败测试**

在 `tests/test_download_cancellation_unittest.py` 增加：

```python
async def test_cancel_client_active_tasks_marks_cancel_requested(self):
    with tempfile.TemporaryDirectory() as tmp:
        downloader = Downloader(download_dir=Path(tmp), cookies_file=None)
        qm = QueueManager(downloader, max_concurrent=1)
        started = asyncio.Event()
        release = asyncio.Event()

        async def fake_download(task, callback):
            task.status = "downloading"
            started.set()
            await release.wait()

        downloader.download = fake_download
        task = await qm.add_task("https://example.com/v", "client-a")
        await started.wait()

        cancelled = qm.cancel_client_tasks("client-a", "退出登录时取消")

        self.assertEqual(cancelled, 1)
        self.assertTrue(task.cancel_requested)
        self.assertEqual(task.status, "cancelled")
        release.set()
```

- [ ] **步骤 2：运行测试确认失败**

运行：

```powershell
venv\Scripts\python.exe -m unittest tests.test_download_cancellation_unittest
```

预期：失败，提示 `cancel_client_tasks` 不存在。

- [ ] **步骤 3：实现取消入口**

增加：

```python
def cancel_task(self, task_id: str, client_id: str | None = None, reason: str = "下载已取消") -> bool:
    task = self.downloader.get_task(task_id)
    if not task:
        return False
    if client_id is not None and task.client_id != client_id:
        return False
    if task.status not in ("pending", "downloading"):
        return False
    task.request_cancel(reason)
    task.status = "cancelled"
    runner = self._running_tasks.get(task_id)
    if runner and not runner.done():
        runner.cancel()
    self.downloader.cleanup_download_artifacts(task)
    self.downloader.cleanup_temp_files(task.task_id)
    return True

def cancel_client_tasks(self, client_id: str, reason: str = "下载已取消") -> int:
    return sum(
        1 for task in self.get_active_tasks_for_client(client_id)
        if self.cancel_task(task.task_id, client_id=client_id, reason=reason)
    )

def cancel_guest_session_tasks(self, session_id: str, reason: str = "游客会话已关闭") -> int:
    return sum(
        1 for task in self.get_active_tasks_for_guest_session(session_id)
        if self.cancel_task(task.task_id, reason=reason)
    )
```

如果直接 `runner.cancel()` 导致测试中的假下载抛 `CancelledError` 冒泡，需要在 `_execute_with_semaphore()` 中吞掉取消并记录日志。

- [ ] **步骤 4：运行测试确认通过**

运行：

```powershell
venv\Scripts\python.exe -m unittest tests.test_download_cancellation_unittest
```

预期：通过。

- [ ] **步骤 5：提交**

```powershell
git add server/queue_manager.py tests/test_download_cancellation_unittest.py
git commit -m "feat(下载): 增加任务取消入口"
```

---

## 任务 9.5：服务端取消 API

**文件：**
- 修改：`server/api.py`
- 测试：`tests/test_download_cancellation_unittest.py`

- [ ] **步骤 1：增加 API 契约测试**

在 `tests/test_download_cancellation_unittest.py` 增加静态契约测试：

```python
def test_api_exposes_cancel_endpoints(self):
    source = (Path(__file__).resolve().parents[1] / "server" / "api.py").read_text(encoding="utf-8")

    self.assertIn('@router.get("/tasks/active"', source)
    self.assertIn('@router.post("/tasks/{task_id}/cancel"', source)
    self.assertIn('@router.post("/tasks/cancel-active"', source)
```

- [ ] **步骤 2：运行测试确认失败**

运行：

```powershell
venv\Scripts\python.exe -m unittest tests.test_download_cancellation_unittest
```

预期：失败，提示 endpoint 不存在。

- [ ] **步骤 3：实现 API**

在 `server/api.py` 增加：

```python
@router.get("/tasks/active", response_model=list[TaskResponse])
async def get_active_tasks(client_id: str = Query(...), qm: QueueManager = Depends(get_queue_manager)):
    return [_task_to_response(t) for t in qm.get_active_tasks_for_client(client_id)]


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str, client_id: str = Query(...), qm: QueueManager = Depends(get_queue_manager)):
    if not qm.cancel_task(task_id, client_id=client_id, reason="用户取消下载"):
        raise HTTPException(status_code=404, detail="任务不存在、无权取消或已不可取消")
    return {"status": "ok"}


@router.post("/tasks/cancel-active")
async def cancel_active_tasks(client_id: str = Query(...), qm: QueueManager = Depends(get_queue_manager)):
    count = qm.cancel_client_tasks(client_id, reason="退出登录时取消")
    return {"status": "ok", "cancelled_count": count}
```

注意路由顺序：`/tasks/cancel-active` 必须放在 `/tasks/{task_id}/cancel` 之前，避免路径匹配歧义。

- [ ] **步骤 4：运行测试确认通过**

运行：

```powershell
venv\Scripts\python.exe -m unittest tests.test_download_cancellation_unittest
```

预期：通过。

- [ ] **步骤 5：提交**

```powershell
git add server/api.py tests/test_download_cancellation_unittest.py
git commit -m "feat(下载): 增加取消下载 API"
```

---

## 任务 9.6：游客断开后取消活跃下载

**文件：**
- 修改：`server/main.py`
- 测试：`tests/test_download_cancellation_unittest.py`

- [ ] **步骤 1：增加静态契约测试**

在 `tests/test_download_cancellation_unittest.py` 增加：

```python
def test_guest_disconnect_cleanup_cancels_active_tasks_before_directory_cleanup(self):
    source = (Path(__file__).resolve().parents[1] / "server" / "main.py").read_text(encoding="utf-8")

    cancel_idx = source.find("cancel_guest_session_tasks")
    cleanup_idx = source.find("cleanup_guest_session")

    self.assertGreaterEqual(cancel_idx, 0)
    self.assertGreater(cleanup_idx, cancel_idx)
```

- [ ] **步骤 2：运行测试确认失败**

运行：

```powershell
venv\Scripts\python.exe -m unittest tests.test_download_cancellation_unittest
```

预期：失败，提示 `cancel_guest_session_tasks` 未出现在 `main.py`。

- [ ] **步骤 3：调整 delayed cleanup**

在 `server/main.py` 的 `_delayed_cleanup()` 中，在清理目录前增加：

```python
cancelled = queue_mgr.cancel_guest_session_tasks(session_id, reason="游客页面已关闭")
logger.info("已取消 %d 个 guest session 活跃下载: %s", cancelled, session_id)
```

然后再调用：

```python
cleaned = queue_mgr.downloader.cleanup_guest_session(session_id)
```

- [ ] **步骤 4：运行测试确认通过**

运行：

```powershell
venv\Scripts\python.exe -m unittest tests.test_download_cancellation_unittest
```

预期：通过。

- [ ] **步骤 5：提交**

```powershell
git add server/main.py tests/test_download_cancellation_unittest.py
git commit -m "fix(游客): 关闭页面后取消活跃下载"
```

---

## 任务 9.7：前端退出登录确认与取消调用

**文件：**
- 修改：`www/download.js`
- 可选修改：`www/download.html`
- 测试：`tests/test_frontend_session_contract_unittest.py`

- [ ] **步骤 1：编写失败测试**

在 `tests/test_frontend_session_contract_unittest.py` 增加：

```python
def test_logout_checks_active_downloads_before_clearing_session(self):
    source = read_text("www/download.js")

    self.assertIn("getActiveDownloads", source)
    self.assertIn("/api/tasks/active", source)
    self.assertIn("cancelActiveDownloads", source)
    self.assertIn("/api/tasks/cancel-active", source)
```

- [ ] **步骤 2：运行测试确认失败**

运行：

```powershell
venv\Scripts\python.exe -m unittest tests.test_frontend_session_contract_unittest
```

预期：失败，提示函数或 API 字符串不存在。

- [ ] **步骤 3：实现前端逻辑**

在 `www/download.js` 增加：

```javascript
async function getActiveDownloads() {
    const res = await fetch(`/api/tasks/active?client_id=${encodeURIComponent(clientId)}`, {
        headers: authHeaders(),
    });
    if (!res.ok) return [];
    return await res.json();
}

async function cancelActiveDownloads() {
    const res = await fetch(`/api/tasks/cancel-active?client_id=${encodeURIComponent(clientId)}`, {
        method: 'POST',
        headers: authHeaders(),
    });
    if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || '取消下载失败');
    }
}
```

修改 `logout()`：

```javascript
async function logout() {
    const activeDownloads = await getActiveDownloads();
    let shouldCancel = false;
    if (activeDownloads.length > 0) {
        shouldCancel = confirm(`当前有 ${activeDownloads.length} 个下载任务正在进行。\n\n确定取消这些下载并退出吗？\n\n选择“取消”将继续后台下载并退出登录。`);
    } else if (!confirm('确定要退出登录吗？')) {
        return;
    }
    if (shouldCancel) {
        await cancelActiveDownloads();
    }
    // 保留现有退出逻辑
}
```

如果后续需要更好的双按钮文案，再用自定义模态框替换 `confirm()`。

- [ ] **步骤 4：运行测试和语法检查**

运行：

```powershell
venv\Scripts\python.exe -m unittest tests.test_frontend_session_contract_unittest
node --check www\download.js
```

预期：通过。

- [ ] **步骤 5：提交**

```powershell
git add www/download.js tests/test_frontend_session_contract_unittest.py
git commit -m "feat(前端): 退出登录时处理活跃下载"
```

---

## 任务 9.8：文档、工作日志与手工检查清单

**文件：**
- 创建：`docs/superpowers/worklogs/2026-04-18-task-9-download-lifecycle.md`
- 修改：`docs/superpowers/frontend-session-checklist.md`

- [ ] **步骤 1：创建工作日志**

写入：

```markdown
# 任务 9 工作日志：下载生命周期与中断机制

## 背景

下载任务此前由页面连接间接驱动，缺少可靠取消机制。

## 本次策略

- 游客关闭页面：30 秒宽限期后取消下载并清理。
- 登录用户关闭页面：继续后台下载。
- 登录用户主动退出：询问继续后台下载或取消。

## 验证

- `venv\Scripts\python.exe -m unittest tests.test_download_cancellation_unittest`
- `venv\Scripts\python.exe -m unittest tests.test_downloader_transfer_boundaries_unittest`
- `venv\Scripts\python.exe -m unittest tests.test_frontend_session_contract_unittest`
- `node --check www\download.js`
```

- [ ] **步骤 2：更新手工检查清单**

在 `docs/superpowers/frontend-session-checklist.md` 增加：

```markdown
## 场景 15：游客下载中关闭页面

预期：
- 30 秒内刷新或重开同一 session 不取消。
- 30 秒后无重连则取消活跃下载。
- 临时视频、音频、part 文件被清理。

## 场景 16：登录用户关闭页面

预期：
- 下载继续后台运行。
- 完成后视频进入该用户视频库。

## 场景 17：登录用户下载中退出

预期：
- 前端提示有活跃下载。
- 选择继续后台下载时，任务完成后入库。
- 选择取消下载时，任务状态为已取消且残留清理。
```

- [ ] **步骤 3：运行文档和测试检查**

运行：

```powershell
git diff --check
venv\Scripts\python.exe -m unittest tests.test_download_cancellation_unittest tests.test_downloader_transfer_boundaries_unittest tests.test_frontend_session_contract_unittest
```

预期：通过，`git diff --check` 仅允许 Windows 换行提示。

- [ ] **步骤 4：提交**

```powershell
git add docs/superpowers/worklogs/2026-04-18-task-9-download-lifecycle.md docs/superpowers/frontend-session-checklist.md
git commit -m "docs(下载): 记录下载生命周期检查项"
```

---

## 最终验收

完成全部任务后运行：

```powershell
venv\Scripts\python.exe -m unittest tests.test_download_cancellation_unittest tests.test_downloader_transfer_boundaries_unittest tests.test_frontend_session_contract_unittest
venv\Scripts\python.exe -m unittest tests.test_admin_management_unittest tests.test_auth_roles_unittest tests.test_invites_unittest tests.test_user_library_unittest tests.test_v4_migrations_unittest tests.test_video_library_unittest
node --check www\download.js
venv\Scripts\python.exe -m py_compile server\downloader.py server\queue_manager.py server\api.py server\main.py
git diff --check
```

验收标准：

- 游客关闭页面后不会留下无人认领下载。
- 登录用户关闭页面后下载继续，完成后入库。
- 登录用户退出时可选择继续后台下载或取消下载。
- 取消下载不会误标为失败。
- 分离音视频下载取消后不会留下孤儿音频或 part 文件。
- 已有视频库、复用、容量、分享逻辑不回退。

