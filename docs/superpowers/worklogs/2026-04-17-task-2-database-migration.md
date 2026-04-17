# GoTube v4 任务 2 工作日志：数据库迁移基础

## 基本信息

- **日期：** 2026-04-17
- **范围：** 任务 2：数据库迁移基础
- **目标：** 建立 v4 多用户视频库所需的数据模型和幂等迁移能力，不改变现有下载和播放业务行为。

## 设计调整

根据新增需求，原 `video_assets(owner_user_id, filepath...)` 单表模型调整为双层模型：

- `media_assets`：表示硬盘上的一份物理视频文件。
- `user_video_items`：表示某个用户视频库中引用了某个物理视频。

这样可以支持不同用户拥有同一指纹视频而不重复下载。用户删除视频时先删除自己的视频库条目；只有没有任何活跃用户条目引用该物理视频时，后续删除流程才允许物理删除文件。

分享链接也调整为绑定 `user_video_items.share_token`。后续任务会根据用户视频库条目状态、用户状态和物理文件状态判断分享链接是否有效。

## 已完成改动

### 1. 数据模型

- `users` 增加：
  - `storage_quota_mb`
  - `storage_used_bytes`
- 新增 `SchemaMigration`。
- 新增 `MediaAsset`。
- 新增 `UserVideoItem`。
- 新增 `InviteCode`。

### 2. 幂等迁移

新增 `server/migrations.py`：

- 补齐旧库缺失的用户容量列。
- 创建 `schema_migrations`、`media_assets`、`user_video_items`、`invite_codes`。
- 将历史 `readonly` 用户迁移为 `user`。
- 扫描旧下载目录，将 legacy 视频登记到 `media_assets`。
- 跳过 `temp_guest`、`.temp_ytdlp`、非视频文件和符号链接。
- 通过 `schema_migrations` 记录 v4 迁移，重复启动不重复登记。

### 3. 启动接入

`init_db()` 在 `Base.metadata.create_all()` 后执行 `run_v4_migrations()`。新库直接创建完整表结构，旧库通过迁移补齐字段和表。

### 4. 测试

新增 `tests/test_v4_migrations_unittest.py`，使用标准库 `unittest`，避免依赖当前环境未安装的 `pytest`。

覆盖内容：

- v4 表结构存在。
- `readonly` 用户迁移为 `user`。
- legacy 视频只登记到 `media_assets`。
- 重复迁移不重复登记。
- guest 临时视频不登记。
- 迁移不移动、不删除现有文件。

## 验证记录

- `venv\Scripts\python.exe -m unittest tests.test_v4_migrations_unittest -v`：通过，2 个测试通过。
- `venv\Scripts\python.exe -m compileall server`：通过。
- `venv\Scripts\python.exe -c "from server.main import app; print(app.title)"`：通过，输出 `GoTube`。
- 本地启动检查：通过。临时端口启动后，主页返回 200，下载页返回 200，`/api/downloads` 返回 403。
- 本地数据库迁移检查：`schema_migrations`、`media_assets`、`user_video_items`、`invite_codes` 均已存在，v4 版本记录存在，`media_assets=1`，`user_video_items=0`。

## 备份记录

- 启动验证前已备份本地数据库：`backups/gotube-before-v4-task2-20260417-123921.db`。

## 当前遗留

- 任务 2 只落数据库底座，不启用下载去重业务流。
- `user_video_items.share_token` 的生成、分享播放和失效判断放到后续视频库服务任务中实现。
- 用户删除视频时「先删库条目，再按引用数决定是否物理删除」放到后续视频库服务任务中实现。
- 容量统计仍未接入业务逻辑，后续应基于活跃 `user_video_items` 关联的 `media_assets.size_bytes` 计算。
