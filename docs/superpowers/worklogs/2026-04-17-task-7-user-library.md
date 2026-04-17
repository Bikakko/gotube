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

## 修复记录：登录态隔离与首页入口

用户继续验收反馈后修复：

- 普通用户退出后再登录管理员仍看到普通用户界面：
  - 退出登录会调用服务端 `/auth/logout` 使 token 失效；
  - 本地清空当前用户、视频库、容量、任务卡片；
  - 旋转 `client_id` 并重连 WebSocket，避免继续复用上一位用户的下载任务视图。
- 切换账号时可能残留上一账号任务：
  - 登录成功后如果用户 ID 发生变化，主动切换本地 client 会话。
  - WebSocket 主动重连时清理旧连接的重连计时器和心跳，避免旧 client 恢复后混入任务流。
- 根路径不再强制显示登录框：
  - `/` 改为公开首页占位；
  - 下载入口保留为隐藏路径链接，后续可继续扩展公开内容。
- 登录框风格不一致：
  - 去掉登录/注册模态框主要内联样式；
  - 改为下载页统一的按钮、输入框、错误提示样式。
- 用户界面退出按钮位置和操作确认：
  - 登录状态栏移到页面右上角边缘；
  - 退出登录增加二次确认。

追加验证：

- `node --check www\download.js`
- `git diff --check`
- 临时 `uvicorn server.main:app --port 8766` 启动检查：
  - `/health` 返回 200；
  - `/` 返回 200，且不包含 `login-section` / `handleLogin` / `gotube_admin_token`；
  - `/` 包含下载页入口 `download-link`；
  - `/7777` 返回 200。

## 修复记录：管理员不进入普通用户视频库上下文

用户继续验收反馈后修复：

- 明确 `role=user` 才是“我的视频库”用户：
  - 下载页只有普通用户加载和渲染“我的视频库”；
  - 管理员登录下载页时隐藏个人库区域，只保留下载入口和“管理后台”入口；
  - 管理员点击 GoTube 标识进入管理后台，不再滚动到个人库。
- 后端增加同一边界：
  - `/api/me/quota`、`/api/me/videos`、个人库删除、分享开关、下载、缩略图接口均拒绝管理员；
  - 游客转存到个人库也只允许普通用户；
  - 管理员在下载页提交任务不再绑定为个人视频库条目。
- 新增回归测试覆盖管理员访问 `/api/me/*` 被拒绝。

追加验证：

- `venv\Scripts\python.exe -m unittest tests.test_user_library_unittest -v`
- `node --check www\download.js`
- `venv\Scripts\python.exe -m compileall server`
- `git diff --check`
- `venv\Scripts\python.exe -m unittest tests.test_user_library_unittest tests.test_admin_management_unittest tests.test_auth_roles_unittest tests.test_video_library_unittest -v`

## 修复记录：游客 session 生命周期和转存入库

用户继续验收反馈后修复：

- 路人用户关闭窗口后临时视频不删除：
  - 服务端 WebSocket guest 清理从“最后连接时间”改为“活跃连接计数”；
  - 断开后延迟 30 秒，只在该 session 无活跃连接时清理，避免 30 秒边界误判后永久保留。
- 关闭窗口后再次登录会转入之前路人的视频：
  - 前端 guest session 改为 `sessionStorage`，刷新保留、关闭标签页后失效；
  - 启动时清理旧版 `localStorage` guest session，避免旧路人 session 被新登录用户复用。
- 停留下载页时登录转存后不出现在用户视频库：
  - guest 转存移动文件后，服务端把转入主目录的文件注册为当前普通用户的 `UserVideoItem`；
  - 回填任务的 `user_video_item_id`、`media_asset_id`、`share_token`；
  - 前端显示“转移数量 / 入库数量”，转存成功后刷新我的视频库并轮换 guest session。
- 转存目标文件已存在时清理重复 guest 目录，避免临时目录残留。

追加验证：

- `venv\Scripts\python.exe -m unittest tests.test_user_library_unittest -v`
- `node --check www\download.js`
- `venv\Scripts\python.exe -m compileall server`
- `git diff --check`
- `venv\Scripts\python.exe -m unittest tests.test_user_library_unittest tests.test_admin_management_unittest tests.test_auth_roles_unittest tests.test_video_library_unittest tests.test_v4_migrations_unittest tests.test_invites_unittest -v`
- 临时 `uvicorn server.main:app --port 8766` 启动检查：
  - `/health` 返回 200；
  - `/7777` 返回 200；
  - `/static/download.js` 返回 200，包含 `sessionStorage` 和旧 `localStorage` guest session 清理。

未执行：

- `pytest tests\test_security_boundaries.py`：当前 venv 未安装 `pytest`。

## 修复记录：复用、容量和界面增长问题

用户继续验收反馈后修复：

- 用户界面会随视频增多变长：
  - “我的视频库”增加前端分页，每页 8 个视频。
- 不同用户或游客下载视频库已有 URL 仍走下载：
  - 新增按来源 URL 读取已有媒体资产的服务函数；
  - 普通用户继续直接创建自己的视频库条目；
  - 游客命中已有媒体资产时创建完成态 guest 占位任务，不再启动下载。
- 游客并发同视频时互相误伤：
  - 全局 hash 去重索引排除 `temp_guest`，避免游客 2 复用游客 1 的临时文件；
  - guest 转存支持 `DUPLICATE` 占位任务，即使 session 目录没有实体视频也能转入用户库。
- 登录用户下载完成后容量超限：
  - 用户库注册失败时，如果是本次新下载的非重复文件，删除落盘文件和目录；
  - 避免“文件已落盘但无法入库”的残留状态。
- 管理员退出登录：
  - admin 退出后跳转到 `/`，不再停留在 `/admin` 并弹登录框。

追加验证：

- `venv\Scripts\python.exe -m unittest tests.test_user_library_unittest tests.test_video_library_unittest -v`
- `node --check www\download.js www\admin\js\auth.js`
- `venv\Scripts\python.exe -m compileall server`
- `git diff --check`
- `venv\Scripts\python.exe -m unittest tests.test_user_library_unittest tests.test_admin_management_unittest tests.test_auth_roles_unittest tests.test_video_library_unittest tests.test_v4_migrations_unittest tests.test_invites_unittest -v`
- 临时 `uvicorn server.main:app --port 8766` 启动检查：
  - `/health` 返回 200；
  - `/static/download.js` 返回 200，包含 `libraryPageSize`；
  - `/static/admin/js/auth.js` 返回 200，退出后跳转 `/`。

## 修复记录：URL 归一化、游客转存提示与容量失败循环

用户继续验收反馈后修复：

- URL 复用受播放进度参数影响：
  - 来源 URL 归一化时剔除 `t`、`start`、`time_continue`、`progress`、`seek` 等播放进度参数；
  - 同时剔除常见分享跟踪参数，如 `vd_source`、`spm_id_from`、`share_source` 等；
  - 保留语义参数，例如 B 站分 P 参数 `p`，避免误把不同内容合并。
- 游客下载后以管理员账号登录无法保存：
  - `/api/guest-downloads/{session_id}/transfer` 允许当前登录用户为管理员；
  - 前端登录后不再只给普通用户触发游客转存，管理员转存成功后提示去管理后台查看。
- 游客下载后登录但剩余容量不足时提示缺失：
  - 转存注册失败时返回 `errors` 和稳定的 `registered_count=0`；
  - 前端展示“游客视频未入库：容量不足”一类明确提示；
  - 未入库的新转存文件会清理，避免残留孤儿文件。
- 下载后超过容量导致反复重试循环：
  - 后端容量失败仍拒绝入库，不虚增已用容量；
  - 对应下载任务会回填为 `failed`，并携带容量错误，避免继续显示成已完成；
  - 前端识别容量不足错误，不再显示“重试”按钮，避免同一个失败任务反复落盘失败；
  - 普通用户释放空间后需要重新提交下载或重新触发保存。
- 游客之间临时空间互相复用：
  - 本轮仍不做跨 guest 临时任务合并；
  - 维持主库已有 URL 的复用，避免临时文件归属和关闭窗口清理互相误伤。

追加验证：

- `venv\Scripts\python.exe -m unittest tests.test_video_library_unittest tests.test_user_library_unittest -v`
- `node --check www\download.js`
- `venv\Scripts\python.exe -m compileall server`
- `git diff --check`
- `venv\Scripts\python.exe -m unittest discover -s tests -v`
  - 业务相关 32 个 unittest 通过；
  - `tests/test_security_boundaries.py` 因当前 venv 未安装 `pytest` 导入失败，未能在 discover 中执行。
- `venv\Scripts\python.exe -m unittest tests.test_user_library_unittest tests.test_admin_management_unittest tests.test_auth_roles_unittest tests.test_video_library_unittest tests.test_v4_migrations_unittest tests.test_invites_unittest -v`

## 修复记录：容量最后一个视频入库语义

用户指出旧规则会在“剩余容量小于当前视频大小”时拒绝入库，导致视频库无法真正达到满额状态，并允许用户反复尝试下载但总是失败。修正为：

- 容量判断从 `当前已用 + 当前视频大小 <= 配额` 改为 `当前已用 < 配额`；
- 用户未满额时允许保存最后一个视频，即便保存后已用容量超过配额；
- 用户已满额或已超额后，再保存新视频才返回“容量不足”；
- 已用容量仍然由实际入库视频求和刷新，不做虚增；
- guest 转存容量失败测试改为“用户已经满额后再转存才失败”。

追加验证：

- `venv\Scripts\python.exe -m unittest tests.test_video_library_unittest tests.test_user_library_unittest -v`
- `node --check www\download.js www\admin\js\auth.js`
- `venv\Scripts\python.exe -m compileall server`
- `git diff --check`
- `venv\Scripts\python.exe -m unittest tests.test_user_library_unittest tests.test_admin_management_unittest tests.test_auth_roles_unittest tests.test_video_library_unittest tests.test_v4_migrations_unittest tests.test_invites_unittest -v`

## 修复记录：管理员退出后下载页任务卡泄漏

用户反馈管理员退出登录后，下载页会再次出现已保存的视频卡。排查后按两个来源收敛：

- 下载页本地 `client_id` 存在于 `sessionStorage`，管理后台退出不经过下载页 `logout()`，旧 `client_id` 可能继续被 `/api/tasks` 和 WebSocket 用来拉回已完成任务；
- 下载页切换 client 或退出时，旧 WebSocket 的迟到消息/重连仍可能把旧任务写回本地 `tasks`。

修复：

- 下载页增加认证 client 标记，认证态失效或退出时重置 `client_id` 并清空任务；
- 下载页初始化顺序改为先检查登录态，再加载当前 client 的任务，避免先拉旧任务再发现已退出；
- WebSocket 增加连接代际校验，旧连接的 `open/message/error/close` 事件不会再改写当前页面状态；
- 管理后台登录、退出、token 失效、401、当前用户修改自身密码导致登出时，统一清理下载页 `gotube_client_id` 和认证 client 标记。

追加验证：

- `node --check www\download.js www\admin\js\auth.js www\common.js www\admin\js\users.js`
- `venv\Scripts\python.exe -m unittest tests.test_user_library_unittest tests.test_admin_management_unittest tests.test_auth_roles_unittest tests.test_video_library_unittest tests.test_v4_migrations_unittest tests.test_invites_unittest -v`
- `git diff --check`
