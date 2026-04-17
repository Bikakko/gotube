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
