# 2026-04-17 任务 6：后台管理台重构一期

## 背景

本阶段按 v4 规划推进后台管理台重构一期。用户级 Cookie 能力按用户要求降为最低优先级，本次不实现，只保留现有管理员全局 Cookie 管理。

## 本次实现

### 后端管理 API

- `GET /{hidden_path}/admin/api/users`
  - 增加 `video_count`。
  - 保留并返回 `storage_quota_mb`、`storage_used_bytes`。
  - 明确返回 `is_system_account`，管理员账号仍作为系统账号保护。
- `PUT /{hidden_path}/admin/api/users/{user_id}`
  - 支持管理员修改普通用户 `storage_quota_mb`。
  - `null` 表示使用默认容量，`0` 表示不限容量，正整数表示 MB。
  - 管理员账号仍不可通过 Web 管理接口修改。
- `GET /{hidden_path}/admin/api/videos`
  - 增加 `owner=legacy` 过滤未归属媒体。
  - 保留 `owner_user_id` 用户筛选。
  - 默认管理视图返回用户库条目和未归属媒体。
  - 视频条目增加 `owner_user_id`、`owner_username`、`media_asset_id`、`item_id`、`reference_count`、`is_legacy` 等管理字段。

### 后台界面

- 导航改为明确的管理视图入口：
  - 视频管理；
  - 用户管理；
  - 邀请码。
- 视频管理：
  - 增加归属筛选：全部、未归属、指定用户。
  - 视频卡片显示归属用户和关联条目数。
  - 未归属视频禁用用户分享按钮。
  - 带 `media_asset_id` 的删除操作改为调用维护性删除接口，提示会从所有用户视频库移除并物理删除文件。
- 用户管理：
  - 增加视频数列。
  - 增加容量列，显示已用容量 / 配额。
  - 编辑普通用户时可修改视频库容量。
- 邀请码管理：
  - 新增 `www/admin/js/invites.js`。
  - 支持查看邀请码列表。
  - 支持创建邀请码，明文 code 只在创建后弹窗显示一次。
  - 支持作废邀请码。

## 测试

新增 `tests/test_admin_management_unittest.py`，覆盖：

- 用户列表返回容量、占用和视频数。
- 管理员可修改普通用户容量，但不能修改管理员账号。
- 管理视频列表支持全部、指定用户、未归属三种归属视图。

## 验证记录

- `venv\Scripts\python.exe -m unittest tests.test_admin_management_unittest`
- `node --check www\admin\js\state.js`
- `node --check www\admin\js\data.js`
- `node --check www\admin\js\events.js`
- `node --check www\admin\js\render.js`
- `node --check www\admin\js\users.js`
- `node --check www\admin\js\invites.js`

完整回归和启动检查见本任务最终汇报。
