# 任务 14 工作日志：发布前配置与数据巡检

## 背景

V4.0.0 合并前需要一个管理员可见的运行时巡检入口，用来快速确认发布环境是否具备基本运行条件。重点覆盖 Cookie 运行源、下载目录、数据库、ffmpeg 和 yt-dlp，避免部署后才发现环境缺项。

## 修复内容

- 新增 `server.health_checks.collect_runtime_health()`：
  - 返回项目根目录、Git 分支和提交号。
  - 返回当前运行期 Cookie 源、Cookie 文件是否存在、Cookie 平台诊断摘要。
  - 检查下载目录是否可写。
  - 检查 SQLite 数据库路径是否可打开且具备写入条件。
  - 检查 `ffmpeg` 是否可用，并返回版本首行。
  - 返回 yt-dlp 版本。
  - 聚合阻断项到 `blockers`，便于发布前判断。
- 新增管理员接口：
  - `GET /admin/api/runtime/health`
  - 仅管理员可访问。
- 更新 `.env.example`：
  - 明确 `GOTUBE_COOKIES_FILE` 仅作为首次导入旧 Cookie 使用。
  - 运行期 Cookie 由 `data/cookies.txt` 管理。
- 更新 `docs/superpowers/frontend-session-checklist.md`：
  - 增加发布前运行巡检条目。

## 回归测试

新增 `tests/test_health_checks_unittest.py`，覆盖：

- 运行巡检返回 `cookie_source`、`download_dir_writable`、`database_writable`、`ffmpeg_available`、`yt_dlp_version` 和 `blockers` 等关键字段。
- 诊断结果不泄露 Cookie 值。
- 未配置 Cookie 时返回 `cookie_source=none`，并保留稳定的诊断结构。

已运行：

```powershell
.\venv\Scripts\python.exe -m unittest tests.test_health_checks_unittest
.\venv\Scripts\python.exe -m unittest tests.test_health_checks_unittest tests.test_cookie_store_unittest
.\venv\Scripts\python.exe -m py_compile server\health_checks.py server\admin_api.py
```

结果均通过。

## 后续注意

- `database_writable` 不会修改业务表结构；它通过路径权限和 SQLite 连接能力判断。
- `blockers` 为空代表基础运行条件通过，不代表平台下载一定成功。平台风控、Cookie 账号状态、代理质量仍需结合实际下载验证。
