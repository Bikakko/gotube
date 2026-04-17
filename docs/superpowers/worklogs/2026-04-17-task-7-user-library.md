# 2026-04-17 任务 7：普通用户端视频库闭环

## 背景

任务 7 聚焦普通用户端体验收口。后端已经具备多用户视频库、容量、分享 token、按引用删除等能力，本阶段把这些能力接入下载页，形成普通用户可见、可操作的闭环。

## 本次实现

### 后端

- 新增 `UpdateShareRequest`。
- 新增 `PATCH /api/me/videos/{item_id}/share`：
  - 当前用户开启或关闭自己的视频库条目分享。
  - 关闭后原 `share_token` 立即失效。
- 新增 `GET /api/me/videos/{item_id}/download`：
  - 当前用户下载自己的视频库条目。
  - 不通过 filename 暴露主视频库路径。
- `delete_user_video_item()` 和用户库下载/分享服务统一按“当前用户自己的条目”校验。
  - 即使管理员调用 `/api/me/...`，也只能操作自己的库条目。
  - 管理员维护性删除仍走后台 `media-assets` 接口。
- 新增服务函数：
  - `set_user_video_share_enabled()`；
  - `get_user_video_asset_for_download()`。

### 下载页

- 登录后显示“我的视频库”区域。
- 调用 `/api/me/quota` 显示容量。
- 调用 `/api/me/videos` 显示当前用户自己的视频条目。
- 视频条目支持：
  - 播放；
  - 复制分享链接；
  - 认证下载；
  - 开启/关闭分享；
  - 从我的视频库移除。
- 普通用户播放和分享优先使用用户级 `share_token`，不再优先复制裸 `file_hash`。
- 登录用户提交下载任务和重试任务时带 Bearer token，确保下载进入个人视频库流程。
- 登录后游客临时下载转存完成会刷新个人视频库。

## 测试

新增 `tests/test_user_library_unittest.py`，覆盖：

- 当前用户可开启/关闭自己的分享，`resolve_share_token()` 跟随 `share_enabled` 状态变化。
- 用户不能关闭或下载其他用户的视频库条目。
- API 层下载和分享开关使用当前用户权限。

## 验证记录

- `venv\Scripts\python.exe -m unittest tests.test_user_library_unittest`
- `venv\Scripts\python.exe -m unittest tests.test_user_library_unittest tests.test_video_library_unittest -v`
- `node --check www\download.js`

完整回归和启动检查见本任务最终汇报。

## 修复记录：普通用户端回归问题

用户验收反馈后修复：

- 分享链接无法播放：
  - `watch.html` 优先调用 `/api/share/{share_token}/info`；
  - 失败后再兼容旧 `/api/video/{hash}/info`。
- 分享下载和个人库下载文件无后缀：
  - 新增 `/api/share/{share_token}/download`；
  - 认证下载和分享下载都使用保留后缀的下载文件名；
  - 前端 Blob 下载从 `Content-Disposition` 读取文件名，失败时再用标题加原始扩展名兜底。
- 下载任务卡片和视频库卡片功能重叠：
  - 登录用户的已完成任务卡片只提供“在视频库管理”入口；
  - 播放、分享、下载、移除集中到“我的视频库”卡片。
- 视频库卡片无预览：
  - 用户库条目返回 `thumbnail_url`；
  - 前端带 Bearer token 拉取缩略图 blob 后渲染。
- 普通用户登录后仍跳转管理页：
  - logo 登录后只滚动到“我的视频库”；
  - 管理员入口改为独立“管理后台”按钮。
- 缺少退出登录：
  - 下载页新增登录状态栏和“退出登录”按钮。

追加验证：

- `venv\Scripts\python.exe -m unittest tests.test_user_library_unittest -v`
- `venv\Scripts\python.exe -m unittest tests.test_user_library_unittest tests.test_admin_management_unittest tests.test_invites_unittest tests.test_auth_roles_unittest tests.test_v4_migrations_unittest tests.test_video_library_unittest -v`
- `venv\Scripts\python.exe -m compileall server`
- `node --check www\download.js`
- `git diff --check`
- 临时 `uvicorn server.main:app --port 8766` 启动检查：
  - `/health` 返回 200；
  - `/{hidden_path}` 返回 200；
  - `/watch?v=not-a-token` HTML 入口返回 200；
  - `/api/share/not-a-token/info` 返回 404。
