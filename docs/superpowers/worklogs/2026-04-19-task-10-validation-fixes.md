# 任务 10 工作日志：手工验收修复

## 背景

任务 10 手工验收进入第 8 组“下载中断与关闭页面”后，发现两个问题：

- 游客关闭页面后，服务端虽然收到 WebSocket 断开，但运行中的 yt-dlp 任务可能继续写入一段时间，随后留下 `.part` 临时文件。
- 登录用户在下载中退出登录时，前端只有原生确认框的两个分支，缺少“我不想退出登录”的选择；选择取消下载后也可能留下残留文件。

## 根因

运行中的下载由 `asyncio` runner 调度，但实际 yt-dlp 执行在 executor 线程中。原实现取消任务时直接 `runner.cancel()`，这会取消等待 executor 的协程，却不能可靠停止线程里的 yt-dlp。结果是：

- `DownloadTask.cancel_requested` 虽然被设置，但下载协程可能没机会通过 progress hook 观察到取消请求。
- `Downloader.download()` 捕获 `DownloadCancelledError` 的收尾链路被绕过，下载产物和 `.part` 文件清理不稳定。
- Windows 下如果 yt-dlp 线程仍持有文件句柄，立即清理更容易失败。

## 修复策略

- 对 `downloading` 任务：只设置取消请求和前端可见的 `cancelled` 状态，不直接取消 runner，让 yt-dlp progress hook 抛出取消异常后走完整下载清理链路。
- 对 `pending` 任务：仍然可以取消 runner，因为还没有进入 yt-dlp 写文件阶段。
- 在 runner 进入信号量后增加取消请求检查，避免已取消的排队任务继续进入下载。
- 前端退出登录改为自定义三选项确认：
  - 取消下载并退出
  - 保留下载并退出
  - 不退出

## 验证记录

已增加并运行回归测试：

```powershell
venv\Scripts\python.exe -m unittest tests.test_download_cancellation_unittest tests.test_frontend_session_contract_unittest
```

新增覆盖点：

- 取消运行中任务时，下载协程必须能观察到 `cancel_requested` 并自然完成。
- 退出登录存在三种明确分支，且包含“不退出”路径。

## 手工复测重点

- 8.1：游客长下载中关闭标签页，超过宽限期后应取消任务，并清理 `.part` 残留。
- 8.4：登录用户下载中退出登录，选择“取消下载并退出”后应退出成功，并清理残留文件。
- 8.5：登录用户下载中退出登录，选择“保留下载并退出”后，下载应继续后台完成并归属原用户。
- 新增交互：下载中点击退出登录，再选择“不退出”或按 Esc，应保持当前登录状态和下载状态。

## 已知边界

- yt-dlp 的中断仍依赖下一次 progress hook 触发；极少数平台如果长时间没有进度回调，物理清理会延后到下载线程恢复响应后执行。
- 立即重新下载同一 URL 时，yt-dlp 可能复用未清理完成的 `.part` 文件；这属于取消尚未完成收尾期间的竞态，后续如仍高频出现，可以增加“取消中的任务锁”或 orphan 扫描清理。
