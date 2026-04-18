# 前端会话状态检查清单

本文用于任务 8 之后的手工验收和回归模拟。每次修改登录、下载页、管理后台、游客转存、WebSocket 相关逻辑后，都应至少抽样执行这里的场景。

## 准备

- 启动服务，确认 `/health` 返回正常。
- 准备 3 个身份：
  - 游客：不登录。
  - 普通用户 A：有可用容量。
  - 管理员。
- 浏览器打开 DevTools，观察：
  - Console 是否报错；
  - Network 中 `/api/tasks`、`/ws`、`/auth/check` 是否符合预期；
  - Application 中 `sessionStorage` 的 `gotube_client_id` 是否按场景轮换。

## 场景 1：游客进入下载页

步骤：

1. 清空浏览器该站点 localStorage 和 sessionStorage。
2. 打开下载页。
3. 不登录，刷新页面一次。

预期：

- `gotube_client_id` 存在，刷新后保持不变；
- `gotube_guest_session_id` 存在，刷新后保持不变；
- localStorage 不应保存旧 guest session；
- WebSocket URL 包含 `client_id` 和 `session_id`；
- 页面不显示用户视频库；
- 任务列表只包含当前 guest client 的任务。

## 场景 2：游客关闭标签页后重新打开

步骤：

1. 以游客打开下载页，记录 `gotube_guest_session_id`。
2. 关闭该标签页。
3. 新开标签页进入下载页。

预期：

- 新标签页生成新的 `gotube_guest_session_id`；
- 不会把上一标签页游客视频转存给新登录用户；
- WebSocket 使用新的 guest session。

## 场景 3：游客下载后登录普通用户

步骤：

1. 游客下载一个视频，等待完成。
2. 在同一标签页登录普通用户 A。

预期：

- 登录后调用 guest transfer；
- 成功转存后 toast 显示保存到视频库；
- guest session 轮换；
- 视频出现在普通用户 A 的视频库；
- 任务卡补齐 `user_video_item_id` / `share_token`；
- 刷新页面后仍能在用户库看到视频。

## 场景 4：游客下载后登录管理员

步骤：

1. 游客下载一个视频，等待完成。
2. 在同一标签页登录管理员。
3. 进入管理后台。

预期：

- 登录后调用 guest transfer；
- toast 显示已保存到管理后台；
- 下载页不显示“我的视频库”；
- 管理后台能看到该视频；
- 管理员退出后回到首页，再进入下载页，不出现旧管理员任务卡。

## 场景 5：普通用户退出再登录管理员

步骤：

1. 登录普通用户 A。
2. 下载或复用一个视频，确认用户库有条目。
3. 点击下载页退出登录。
4. 登录管理员。

预期：

- 普通用户退出后 `gotube_client_id` 轮换；
- 任务列表清空；
- 管理员登录后下载页不显示普通用户视频库；
- 管理员只看到管理后台入口；
- WebSocket 不会收到普通用户 A 的旧任务。

## 场景 6：管理后台退出后进入下载页

步骤：

1. 登录管理员并进入管理后台。
2. 点击管理后台退出。
3. 从首页进入下载页。

预期：

- localStorage 中没有 `gotube_admin_token`；
- 下载页生成新的 `gotube_client_id`；
- 任务列表不会出现管理员之前的已完成任务；
- WebSocket URL 带新的 guest session；
- 不显示管理后台入口。

## 场景 7：token 过期或 401

步骤：

1. 登录管理员或普通用户。
2. 手动删除服务端 token，或在浏览器 localStorage 中写入无效 token。
3. 刷新下载页或管理后台。

预期：

- 前端清理 `gotube_admin_token`；
- 下载页认证 client 标记被清理；
- 下载页 `client_id` 被重置；
- 不会拉回认证期间的旧任务；
- 管理后台显示登录框。

## 场景 8：切换普通用户

步骤：

1. 登录普通用户 A，下载或复用一个视频。
2. 退出登录。
3. 登录普通用户 B。

预期：

- A 退出时任务列表清空，`client_id` 轮换；
- B 登录后不显示 A 的任务卡和视频库；
- B 的视频库只显示 B 拥有的条目；
- B 下载同 URL 时可复用已有媒体，但创建的是 B 自己的视频库条目。

## 场景 9：容量最后一个视频

步骤：

1. 设置普通用户 A 较小容量。
2. 在未满额状态下载一个大于剩余容量的视频。
3. 再尝试下载另一个新视频。

预期：

- 第一个视频允许入库；
- 已用容量显示达到或超过配额；
- 第二个新视频被容量规则拒绝；
- 容量不足任务不显示“重试”按钮；
- 释放空间后可以再次提交新下载。

## 场景 10：URL 复用与播放进度参数

步骤：

1. 用普通用户 A 下载 `https://www.youtube.com/watch?v=abc`。
2. 用普通用户 B 下载 `https://www.youtube.com/watch?v=abc&t=42s`。
3. 用包含分享跟踪参数的 B 站链接重复测试，例如 `vd_source`。

预期：

- B 不重新下载已有媒体；
- B 得到自己的视频库条目和分享 token；
- 播放进度参数、分享跟踪参数不影响复用；
- 语义参数如 B 站 `p=2` 不被误删。

## 场景 11：旧 WebSocket 迟到消息

步骤：

1. 打开下载页并登录普通用户。
2. 开始一个下载任务。
3. 在下载过程中退出登录或切换账号。
4. 观察任务列表和 Console。

预期：

- 退出或切换账号后任务列表立即清空；
- 旧 WebSocket 的消息不会把旧任务写回页面；
- 新 WebSocket 使用新的 `client_id`；
- Console 不应出现持续重连旧连接的日志。

## 场景 12：管理后台自改密码

步骤：

1. 管理员进入用户管理，修改自己的密码。
2. 等待页面跳转首页。
3. 进入下载页。

预期：

- token 被清理；
- 下载页 `client_id` 被清理或重置；
- 不显示管理员旧任务卡；
- 需要重新登录。

## 验证命令

每次涉及前端会话代码变更后，至少运行：

```powershell
node --check www\common.js www\download.js www\admin\js\auth.js www\admin\js\users.js
venv\Scripts\python.exe -m unittest tests.test_frontend_session_contract_unittest -v
venv\Scripts\python.exe -m unittest tests.test_user_library_unittest tests.test_admin_management_unittest tests.test_auth_roles_unittest tests.test_video_library_unittest tests.test_v4_migrations_unittest tests.test_invites_unittest -v
git diff --check
```

## 判定原则

- 未登录页面只能使用 guest session 和 guest client。
- 登录态 client 退出后不能继续作为未登录 client 使用。
- 管理后台不直接操作下载页内部 key，只通过 `GoTubeSession` 清理。
- 旧 WebSocket 连接不能修改当前页面状态。
- 视频库归属以用户库记录为准，不以任务卡显示为准。

## 场景 13：极短视频与大文件进度条

步骤：
1. 打开下载页，使用游客或普通用户下载一个极短视频。
2. 不刷新页面，观察任务卡进度、状态和完成提示。
3. 再下载一个体积较大的视频，观察下载开始后的前 3 秒、下载中和完成后状态。

预期：
- 极短视频至少能看到任务进入下载中或很快进入完成态，不需要刷新页面才更新。
- 大文件下载中即使百分比变化不明显，也应持续有进度事件或字节变化反馈。
- WebSocket 不应断连重连风暴。
- 完成后视频卡、下载卡状态一致，不出现“后端已完成、前端仍 pending”的状态。
- 当另一个任务正在下载时，之前已完成的任务播放按钮仍可点击并打开播放弹窗。

## 场景 14：分离音视频与单视频大小限制

步骤：
1. 设置较小的 `GOTUBE_MAX_VIDEO_SIZE_MB`。
2. 下载一个会触发分离音视频的链接，例如 YouTube 或 Bilibili 视频。
3. 使用一个最终合并文件超过限制的视频触发失败。
4. 检查下载目录中同名输出族文件。

预期：
- 能预估大小且确定超限时，应在下载前拒绝，不应开始长时间下载。
- 大小未知时可开始下载，但下载中超过限制应自动停止。
- 最终兜底限制判断以合并文件大小为准，而不是单独视频流或音频流。
- 超限任务显示明确的大小限制错误，包括预计超限或实际超限。
- 失败后不应残留同一输出族的 `.mp4`、`.m4a`、`.webm`、`.part`、`.ytdl`、`.temp` 孤儿文件。
- 其他无关视频文件不应被误删。
