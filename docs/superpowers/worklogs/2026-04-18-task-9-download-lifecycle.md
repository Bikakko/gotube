# 任务 9 工作日志：下载生命周期与中断机制

## 背景

任务 8 修复前端会话串号后，下载任务仍存在生命周期边界不清的问题：游客关闭页面后下载可能继续写入临时目录，登录用户退出时无法选择是否取消正在下载的任务，下载任务也缺少明确的「已取消」状态。

本次任务目标是把下载任务从页面连接驱动的进度显示，推进到服务端可追踪、可取消、可清理的生命周期模型。

## 策略

- 游客关闭页面：保留原有 30 秒宽限期；如果没有重连，先取消该 guest session 的活跃下载，再清理临时目录。
- 登录用户关闭页面：不因 WebSocket 断开而取消下载，允许后台继续完成。
- 登录用户主动退出：退出前查询当前 client 的活跃下载，让用户选择取消下载并退出，或继续后台下载并退出。
- 下载器内部：取消不再归类为失败，而是进入 `cancelled` 状态，并清理 `.part`、音视频分离残留和任务临时文件。

## 完成内容

- `DownloadTask` 增加取消请求字段和 `request_cancel()` 方法。
- `Downloader` 增加 `DownloadCancelledError`，在 progress hook 中响应取消请求。
- `QueueManager` 跟踪运行中的 `asyncio.Task`，增加按 client、guest session、owner 查询活跃任务的能力。
- `QueueManager` 增加单任务取消、当前 client 批量取消、guest session 批量取消入口。
- `server/api.py` 增加：
  - `GET /api/tasks/active`
  - `POST /api/tasks/cancel-active`
  - `POST /api/tasks/{task_id}/cancel`
- `server/main.py` 在 guest session 延迟清理前先取消该 session 的活跃下载。
- `www/download.js` 增加退出登录前的活跃下载查询和取消调用。
- 前端任务卡支持 `cancelled` 状态展示。
- 增加下载生命周期相关单元测试和前端契约测试。

## 验证记录

已在实施过程中分段运行：

```powershell
venv\Scripts\python.exe -m unittest tests.test_download_cancellation_unittest
venv\Scripts\python.exe -m unittest tests.test_downloader_transfer_boundaries_unittest
venv\Scripts\python.exe -m unittest tests.test_frontend_session_contract_unittest
node --check www\download.js
venv\Scripts\python.exe -m py_compile server\downloader.py server\queue_manager.py server\api.py server\main.py
```

最终回归命令见本次任务收尾记录。

## 已知边界

- `yt-dlp` 运行在线程池内时，`runner.cancel()` 不能强制杀死线程；实际中断依赖 progress hook 收到下一次进度事件后抛出取消异常。
- 如果某个平台长时间不触发 progress hook，取消可能不是毫秒级生效，但任务会先进入 `cancelled` 状态，后续下载器回调会继续执行残留清理。
- 当前前端使用原生 `confirm()` 表达「取消下载并退出 / 继续后台下载并退出」两种选择。后续若大修登录框，可替换成一致风格的自定义确认弹窗。

