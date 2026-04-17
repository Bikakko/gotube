# 2026-04-17 任务 4：视频库核心与容量控制

## 背景

本阶段承接 v4 多用户视频库升级，目标是把“物理文件”与“用户视频库归属”拆开：视频目录不记录用户信息，统一由数据库表达用户拥有关系、容量、分享链接和删除语义。

用户补充要求已纳入：

- 用户命中已有物理视频时，仍按该视频大小计入个人视频库容量。
- 下载 URL 不同但文件指纹相同时，完成后追加 URL 来源记录，增强后续复用验证。
- 来源复用必须确认媒体资产、来源索引和物理文件同时有效，避免脏记录造成假复用。
- 管理员需要维护性删除能力：物理删除媒体，并从所有用户视频库、来源索引中移除相关记录。

## 本次实现

### 数据模型

- 新增 `media_sources` 表，用于记录一个物理媒体资产对应的来源 URL。
- `media_sources.normalized_url` 做唯一约束，用于下载前复用判断。
- `media_assets` 继续只表达物理文件，不记录用户归属。
- `user_video_items` 继续表达用户拥有关系和分享 token。

### 服务模块

- 新增 `server/media_fingerprint.py`
  - 统一文件指纹计算，迁移和视频库服务复用。
- 新增 `server/quota.py`
  - 管理普通用户容量。
  - 管理员无容量限制。
  - 用户容量按 active `user_video_items -> media_assets.size_bytes` 计算。
- 新增 `server/video_library.py`
  - 注册下载完成视频。
  - 指纹去重。
  - 来源索引复用和清理。
  - 用户视频库列表。
  - 普通用户删除。
  - 管理员维护性删除。
  - 分享 token 解析。

### 下载流程

- `POST /api/tasks` 支持可选 Bearer token。
- 未登录 + `session_id` 仍走 guest 临时下载。
- 登录用户下载前：
  - 检查当前容量是否已达上限。
  - 按来源索引尝试复用已有媒体。
  - 复用成功时不触发 yt-dlp，直接创建完成态任务和当前用户视频库条目。
- 下载完成后：
  - 注册或复用 `media_assets`。
  - 创建或恢复当前用户的 `user_video_items`。
  - 如果指纹命中已有媒体但 URL 不同，删除重复新文件，并新增 `media_sources` 记录。

### 删除语义

- 普通用户删除：
  - 只软删除自己的 `user_video_items`。
  - 失效自己的分享 token。
  - 只有没有任何 active 引用时，才物理删除媒体文件、缩略图、来源索引和媒体资产。
- 管理员维护性删除：
  - 硬删除所有相关 `user_video_items`。
  - 删除 `media_sources`。
  - 删除 `media_assets`。
  - 删除物理视频、`meta.json`、缩略图和空目录。
  - 重算受影响用户容量。

### API

- 新增 `GET /api/me/quota`
- 新增 `GET /api/me/videos`
- 新增 `DELETE /api/me/videos/{item_id}`
- 新增 `GET /api/share/{share_token}/info`
- 新增 `GET /api/share/{share_token}/thumbnail`
- `/watch?v=` 优先解析用户级 `share_token`，再兼容旧 8 位 `file_hash`。
- 管理端新增 `DELETE /{hidden_path}/admin/api/media-assets/{media_asset_id}`。
- 管理端原有 `DELETE /videos/{filename}` 在命中 `media_assets` 时转入维护性删除。

### 配置

- 新增 `GOTUBE_USER_STORAGE_QUOTA_MB`
  - `0` 表示普通用户默认不限制。
  - 管理员始终不受容量限制。
  - 单用户 `storage_quota_mb` 可覆盖默认值。

## 测试

新增 `tests/test_video_library_unittest.py`，覆盖：

- 共享同一物理媒体时，每个用户仍各自计入容量。
- 来源复用必须要求物理文件仍存在。
- 不同 URL 下载到同一指纹时追加来源索引，并删除重复物理文件。
- 普通用户删除只删除自己的库记录，最后引用消失才物理删除。
- 管理员维护性删除移除所有用户库记录、来源索引和物理文件。

扩展 `tests/test_v4_migrations_unittest.py`：

- legacy 媒体迁移时生成 `media_sources`。
- 已经跑过 v4 迁移的数据库再次启动时，也会为已有 `media_assets.source_url` 回填 `media_sources`。

## 验证记录

- `venv\Scripts\python.exe -m unittest tests.test_video_library_unittest -v`
- `venv\Scripts\python.exe -m unittest tests.test_v4_migrations_unittest tests.test_video_library_unittest -v`
- `venv\Scripts\python.exe -m unittest tests.test_v4_migrations_unittest tests.test_video_library_unittest tests.test_auth_roles_unittest -v`
- `venv\Scripts\python.exe -m compileall server`
- `git diff --check`
- 临时 `uvicorn server.main:app --port 8765` 启动检查：
  - `/health` 返回 200
  - `/api/downloads` 返回 403
  - `/api/me/quota` 未授权返回 401

备注：`venv\Scripts\python.exe -m unittest discover -s tests -v` 目前会被既有 `tests/test_security_boundaries.py` 阻断，因为当前环境未安装 `pytest`。

## 本地数据保护

启动检查前已备份当前数据库：

- `backups/gotube-before-v4-task4-20260417-164712.db`

## 待后续任务处理

- 前端下载页展示 `share_token` 和个人视频库。
- 管理端完整多用户视频库 UI。
- 邀请码注册机制。
- 如果要做到“不同 URL 但同内容也下载前避免网络下载”，需要进一步引入平台视频 ID / 来源归一化增强。
