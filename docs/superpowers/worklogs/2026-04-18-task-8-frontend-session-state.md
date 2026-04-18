# 任务 8 工作日志：前端会话状态治理

## 背景

任务 7 后连续出现登录态、管理员态、游客态和下载任务卡之间的状态串扰：

- 管理员退出后，下载页可能再次出现管理员曾经保存过的视频任务卡；
- 普通用户、管理员、游客之间切换时，`client_id`、guest session、token 清理逻辑分散在多个脚本里；
- WebSocket 旧连接的迟到消息和重连可能写回当前页面状态。

本任务目标是把前端会话边界收敛为统一接口，并建立最小回归约束。

## 本次变更

- 新增 `window.GoTubeSession` 公共会话助手，统一管理：
  - 下载页 `client_id`；
  - 下载页认证 client 标记；
  - guest session；
  - 认证态清理；
  - 下载 client 重置。
- 下载页改为加载 `/static/common.js` 后再加载 `/static/download.js`。
- 下载页不再直接维护 `gotube_client_id` / `gotube_authenticated_client` key：
  - 初始化时先检查登录态，再加载当前 client 的任务；
  - token 缺失且之前是认证 client 时，重置 client 并清空任务；
  - token 失效时，清理认证态并重置 client；
  - 登录成功时标记当前 client 为认证 client；
  - 退出时清理认证态并切换到新 client。
- 管理后台登录、退出、401、当前用户修改自身密码导致登出时，统一调用 `GoTubeSession` 清理下载页会话。
- 下载页 WebSocket 保留连接代际校验，旧连接的 `open/message/error/close` 不再改写当前页面。
- 新增前端会话契约测试：
  - `tests/test_frontend_session_contract_unittest.py`
  - 验证公共 helper 存在；
  - 验证下载页先加载 common；
  - 验证下载页和管理页使用 shared helper 管理认证 client 清理。

## 验证

- `venv\Scripts\python.exe -m unittest tests.test_frontend_session_contract_unittest -v`
- `node --check www\common.js www\download.js www\admin\js\auth.js www\admin\js\users.js`

## 2026-04-18 进度推送与大文件边界补丁

### 背景

手工检查基本通过后，发现两个下载链路边界：

- 极短视频和大文件下载时，前端进度条可能一直不动，需要刷新页面后才看到状态变化。
- 单文件大小限制使用 yt-dlp 的单流 `max_filesize`，在 Bilibili/YouTube 分离音视频场景下不等于最终合并文件大小；失败路径只清理部分临时文件，可能留下孤儿音频或 `.part` 文件。

### 根因

- 下载进度通过后台轮询推送，旧逻辑只在 `progress` 比上次增加至少 1% 时推送。短视频可能在轮询首次触发前已经完成；未知总大小或大文件阶段可能只有 `downloaded_bytes` 变化，百分比不明显。
- `max_filesize` 是 yt-dlp 对单个请求格式的限制，不适合表达“最终视频文件最大大小”。分离音视频下载中，视频流、音频流、合并文件和 `.part` 属于同一输出族，失败时需要按输出族清理。

### 本次变更

- 下载阶段开始和结束都主动推送一次任务状态。
- 进度推送触发条件从“百分比变化”扩展为：
  - 百分比变化达到 1%；
  - 已下载字节数变化；
  - 下载中超过 1 秒没有推送时发送心跳。
- 移除 yt-dlp `max_filesize`，改为下载合并完成后检查最终文件大小。
- 新增 `cleanup_download_artifacts`，按同一输出基础名清理最终文件、分离视频、分离音频、`.part`、`.ytdl`、`.temp` 等下载残留。
- 下载失败路径同时调用完整输出族清理和旧的 task 临时文件清理。
- 文件超限错误直接透出具体大小提示。

### 验证

- `venv\Scripts\python.exe -m unittest tests.test_downloader_transfer_boundaries_unittest`
- `venv\Scripts\python.exe -m unittest tests.test_user_library_unittest tests.test_video_library_unittest tests.test_admin_management_unittest`
- `venv\Scripts\python.exe -m py_compile server\downloader.py`
- `venv\Scripts\python.exe -m unittest tests.test_admin_management_unittest tests.test_auth_roles_unittest tests.test_downloader_transfer_boundaries_unittest tests.test_frontend_session_contract_unittest tests.test_invites_unittest tests.test_user_library_unittest tests.test_v4_migrations_unittest tests.test_video_library_unittest`

说明：`venv\Scripts\python.exe -m unittest discover tests` 仍会因为 `tests/test_security_boundaries.py` 直接依赖未安装的 `pytest` 而报 `ModuleNotFoundError: No module named 'pytest'`。其余 `*_unittest.py` 集合已通过。

## 2026-04-18 播放按钮与单文件大小限制体验补丁

### 背景

进一步手工检查发现：

- 下载页正在下载新任务时，已经下载好的游客文件播放按钮可能存在但点击无反应。
- 仅在最终文件完成后校验大小虽然能避免分离音视频孤儿文件，但体验上会让用户等待完整下载后才失败并删除文件。

### 根因

- 任务卡播放按钮的渲染条件是 `completed + filename`，但 `openModal()` 的点击入口先要求 `file_hash/share_token`。普通 guest 本地文件其实可以直接通过 `filename + guest session` 播放，不应该依赖分享 hash。
- yt-dlp 原生单流大小限制不可用；只做最终文件校验又过晚，需要增加下载前预估和下载中保护。

### 本次变更

- 下载页 `openModal()` 拆分播放条件：
  - guest 本地已完成文件：凭 `temp_guest/...` 文件名走 guest stream；
  - 已入库或去重文件：继续凭 `share_token/file_hash` 走 `/watch`。
- 下载前提取信息时使用和实际下载一致的格式选择，并基于 `requested_formats` 汇总分离音视频预计大小；确定超过单文件限制时直接拒绝，不开始下载。
- 大小未知时允许开始下载，但下载中按同一输出族已落盘大小持续保护，超过限制即由 progress hook 中断 yt-dlp。
- 下载后保留最终合并文件大小兜底校验。

### 验证

- `venv\Scripts\python.exe -m unittest tests.test_downloader_transfer_boundaries_unittest tests.test_frontend_session_contract_unittest`
- `node --check www\download.js`
- `venv\Scripts\python.exe -m py_compile server\downloader.py`
- `venv\Scripts\python.exe -m unittest tests.test_user_library_unittest tests.test_video_library_unittest tests.test_admin_management_unittest`
- `venv\Scripts\python.exe -m unittest tests.test_admin_management_unittest tests.test_auth_roles_unittest tests.test_downloader_transfer_boundaries_unittest tests.test_frontend_session_contract_unittest tests.test_invites_unittest tests.test_user_library_unittest tests.test_v4_migrations_unittest tests.test_video_library_unittest`

## 设计结论

- `client_id` 不等价于登录用户，只是下载页任务视图的本地会话标识；
- 一旦本地会话从认证态退回未登录态，必须丢弃旧 `client_id`，否则 `/api/tasks?client_id=` 会拉回旧任务；
- 认证相关页面不应直接知道下载页的 sessionStorage key，应统一通过 `GoTubeSession` 操作；
- guest session 仍然使用 `sessionStorage`，刷新保留，关闭标签页失效；
- 后续管理后台大修前，应以本任务新增的检查清单作为手工验收基线。
