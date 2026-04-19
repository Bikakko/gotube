# GoTube V4.0.0 最终验收清单

日期：2026-04-19

分支：`codex/v4-multi-user-library`

目标：在合并回 `master` 前，确认 V4 多用户视频库、安全边界、下载生命周期、Cookie 运行源、URL 复用、管理员维护能力和发布前巡检都具备可交付状态。

## 结论

V4.0.0 发布前验收通过，可以进入合并前代码审查和最终部署准备。

本清单只代表当前分支的发布门禁状态。平台侧风控、Cookie 账号状态、代理质量、yt-dlp 上游变更仍属于运行期外部变量，需要通过管理员 Cookie 诊断和实际下载抽检持续确认。

## 自动化验证

### 单元测试

执行命令：

```powershell
.\venv\Scripts\python.exe -m unittest tests.test_download_cancellation_unittest tests.test_cookie_store_unittest tests.test_downloader_error_messages_unittest tests.test_frontend_session_contract_unittest tests.test_downloader_transfer_boundaries_unittest tests.test_admin_management_unittest tests.test_cookie_diagnostics_unittest tests.test_url_normalizer_unittest tests.test_health_checks_unittest
```

结果：

- 通过。
- 共运行 50 个测试。
- 运行时间约 1.9 秒。
- Windows 文件占用兜底测试会输出「移动 guest 文件失败，尝试复制兜底」日志，这是测试用例覆盖的预期路径，不是失败。

说明：

- 原任务 15 计划中写的是 `tests.test_admin_media_unittest`。
- 当前仓库实际测试文件为 `tests.test_admin_management_unittest`。
- 本次最终门禁使用实际存在的管理员后台测试集执行。

### 前端语法检查

执行命令：

```powershell
node --check www\download.js
node --check www\admin\js\cookies.js
node --check www\admin\js\render.js
```

结果：通过，无语法错误输出。

### 后端语法检查

执行命令：

```powershell
.\venv\Scripts\python.exe -m py_compile server\downloader.py server\queue_manager.py server\admin_api.py server\cookie_store.py server\url_normalizer.py server\health_checks.py server\main.py
```

结果：通过，无语法错误输出。

### Diff 检查

执行命令：

```powershell
git diff --check
```

结果：通过。

## 手工验收结论

任务 10 共 9 组手工验收已完成，最终结论为通过。

| 组别 | 内容 | 结论 |
| --- | --- | --- |
| 第 0 组 | 验收准备、健康检查、下载页访问 | 通过 |
| 第 1 组 | 游客基础下载、播放、下载文件名、刷新保持 | 通过 |
| 第 2 组 | 游客转存到普通用户 | 通过 |
| 第 3 组 | 登录态隔离 | 通过 |
| 第 4 组 | 用户视频库与容量 | 通过 |
| 第 5 组 | URL 复用 | 通过 |
| 第 6 组 | 分享链接有效性 | 通过 |
| 第 7 组 | 管理员维护删除 | 通过 |
| 第 8 组 | 下载中断与关闭页面 | 通过 |
| 第 9 组 | 大文件与分离音视频 | 通过 |

## V4 已收口能力

### 安全边界

- `session_id` 已做格式校验和路径边界检查。
- 分享 hash 改为完整格式校验和精确匹配。
- 公开视频管理 API 的危险操作已收紧到授权路径。
- 前端任务卡渲染已避免直接拼接外部标题触发 XSS。
- 游客转存已纳入登录态约束。

### 多用户视频库

- 物理媒体与用户视频库条目分离。
- 不同用户拥有同一物理媒体时，不重复保存物理文件。
- 用户删除视频库条目时，只删除归属关系。
- 最后一个超过剩余容量的视频允许入库，使容量真实达到或超过上限。
- 已满或超额后继续下载新视频会被拒绝。
- 管理员维护性删除会清理物理文件、用户条目和相关分享状态。

### 分享链接

- 分享 token 与用户视频库条目关联。
- 用户关闭分享、删除条目、管理员维护删除后，旧分享失效。
- 其他用户拥有同一物理视频时，分享状态互不影响。

### 下载生命周期

- 游客关闭页面后，未完成下载会在宽限期后取消并清理临时文件。
- 登录用户关闭页面后，下载继续在后台执行，并归属原用户。
- 登录用户退出时支持取消下载并退出、保留下载并退出、不退出。
- 取消下载后会清理 `.part`、`.ytdl`、`.temp` 和同输出族残留。
- 大文件限制可在预估阶段提前拒绝，下载中超限也会停止并清理。

### Cookie 与平台下载

- 运行期 Cookie 统一使用 `data/cookies.txt`。
- 根目录 `cookies.txt` 仅作为旧配置导入来源，不再与运行期上传 Cookie 争夺权限。
- 管理后台提供平台关键字段诊断，不暴露 Cookie 值。
- Bilibili、X/Twitter、YouTube 已通过重新上传有效 Cookie 恢复下载。

### URL 复用

- 增加 URL 规范化模块，去除常见播放进度和跟踪参数。
- 支持 YouTube、Bilibili、X/Twitter 的稳定媒体 key。
- 下载前复用优先使用媒体 key 和规范化 URL。
- 原始 URL 保留用于审计和后续排查。

### 管理后台与发布巡检

- 管理员全局媒体视图按物理媒体聚合。
- 管理页时间筛选已修复。
- Cookie 诊断面板已补齐。
- 管理员运行巡检接口 `/admin/api/runtime/health` 已增加。
- 发布前可检查下载目录、数据库、ffmpeg、yt-dlp、Cookie 诊断和阻断项。

## 发布前人工补测

合并前建议按以下顺序做一次轻量人工复核：

1. 打开 `/health`，确认返回正常。
2. 管理员登录后访问 `/admin/api/runtime/health`，确认 `blockers` 为空。
3. 管理后台 Cookie 诊断中，目标平台关键字段处于可接受状态。
4. 游客下载一个短视频，确认播放和下载可用。
5. 游客下载完成后登录普通用户，确认转存入库。
6. 普通用户 A 与普通用户 B 下载同一 URL，确认复用和各自视频库条目。
7. 用户分享、关闭分享、删除视频库条目后，确认旧分享失效。
8. 管理员维护删除一个多用户共有视频，确认所有用户条目和分享失效。
9. 使用较小 `GOTUBE_MAX_VIDEO_SIZE_MB` 抽测一次超限拒绝提示。
10. 恢复正常大小限制后重启服务，确认普通下载不受影响。

## 合并前门禁

合并回 `master` 前必须满足：

- 当前分支已推送到远端。
- `git status --short` 除明确保留的原始验收反馈文件外没有未提交修改。
- 最终自动化验证命令通过。
- 管理员运行巡检无阻断项。
- 任务 10 手工验收总结和本清单均已提交。
- 如合并前又修改运行逻辑，必须重新执行本清单中的自动化验证。

## 回滚策略

如果 V4 合并后出现严重问题：

1. 暂停新下载任务，保留现有下载目录和数据库文件。
2. 备份当前 SQLite 数据库和 `downloads` 目录。
3. 使用 Git 回滚到合并前的 `master` 提交。
4. 如果已经执行 V4 数据迁移，不直接用旧版本写入新库；应使用备份恢复。
5. 保留 `data/cookies.txt`，但回滚后确认旧版本是否仍读取该路径。
6. 记录触发回滚的请求路径、用户身份、任务 ID、日志片段和数据库状态，再决定是否修复后重新发布。

## 暂不纳入 V4.0.0

- 普通用户个人 Cookie 上传。
- 管理后台完整视觉重做。
- 替代 yt-dlp 的平台解析能力。
- 游戏 Hub 或其他主页独立业务接入。
