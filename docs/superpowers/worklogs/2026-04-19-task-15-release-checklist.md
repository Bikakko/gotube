# 任务 15 工作日志：V4.0.0 最终验收包

## 背景

任务 10 手工验收完成后，任务 11 到任务 14 已陆续收口管理后台聚合、Cookie 诊断、URL 规范化复用和发布前运行巡检。任务 15 的目标是把 V4.0.0 合并前门禁固化成一份可执行清单，避免发布前只依赖口头结论。

## 本次变更

- 新增 `docs/superpowers/v4-release-checklist.md`：
  - 记录最终自动化验证命令和结果。
  - 汇总任务 10 的 9 组手工验收结论。
  - 整理 V4 已收口能力。
  - 明确发布前人工补测顺序。
  - 明确合并前门禁和回滚策略。
  - 标出暂不纳入 V4.0.0 的事项。
- 更新 `docs/superpowers/task-10-acceptance-summary.md`：
  - 将任务 10 中遗留的管理后台、Cookie 诊断、URL 规范化问题标记为已在任务 11 到任务 14 收口。
  - 增加任务 15 发布门禁说明。

## 验证记录

首次执行任务 15 计划中的测试命令时发现：

```text
ModuleNotFoundError: No module named 'tests.test_admin_media_unittest'
```

原因是计划文档中的测试模块名称与当前仓库实际文件不一致。当前仓库实际管理员后台测试文件为 `tests.test_admin_management_unittest`。本次最终门禁改用实际存在的测试模块执行。

最终自动化验证：

```powershell
.\venv\Scripts\python.exe -m unittest tests.test_download_cancellation_unittest tests.test_cookie_store_unittest tests.test_downloader_error_messages_unittest tests.test_frontend_session_contract_unittest tests.test_downloader_transfer_boundaries_unittest tests.test_admin_management_unittest tests.test_cookie_diagnostics_unittest tests.test_url_normalizer_unittest tests.test_health_checks_unittest
```

结果：

- 运行 50 个测试。
- 结果为 `OK`。
- Windows 文件占用兜底测试输出预期日志，不影响测试结果。

```powershell
node --check www\download.js
node --check www\admin\js\cookies.js
node --check www\admin\js\render.js
.\venv\Scripts\python.exe -m py_compile server\downloader.py server\queue_manager.py server\admin_api.py server\cookie_store.py server\url_normalizer.py server\health_checks.py server\main.py
git diff --check
```

结果：全部通过，无错误输出。

## 后续注意

- 合并回 `master` 前，建议按 `docs/superpowers/v4-release-checklist.md` 再做一次轻量人工补测。
- 如果合并前继续修改运行逻辑，必须重新执行任务 15 的自动化门禁。
- 原始手工验收反馈文件仍保持未跟踪状态，本次不纳入提交。
