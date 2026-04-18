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

## 设计结论

- `client_id` 不等价于登录用户，只是下载页任务视图的本地会话标识；
- 一旦本地会话从认证态退回未登录态，必须丢弃旧 `client_id`，否则 `/api/tasks?client_id=` 会拉回旧任务；
- 认证相关页面不应直接知道下载页的 sessionStorage key，应统一通过 `GoTubeSession` 操作；
- guest session 仍然使用 `sessionStorage`，刷新保留，关闭标签页失效；
- 后续管理后台大修前，应以本任务新增的检查清单作为手工验收基线。
