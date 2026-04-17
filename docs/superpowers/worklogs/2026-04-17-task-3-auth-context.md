# GoTube v4 任务 3 工作日志：认证上下文与角色简化

## 基本信息

- **日期：** 2026-04-17
- **范围：** 任务 3：认证上下文与角色简化
- **目标：** 抽取通用认证依赖，消除 `api.py` 对 `admin_api.py` 的反向依赖，并移除 `readonly` 角色入口。

## 已完成改动

### 1. 认证上下文抽取

新增 `server/auth.py`：

- `get_db()`：统一数据库会话依赖。
- `verify_token()`：校验 Token 并返回认证 payload。
- `get_current_user()`：从 Bearer Token 获取当前登录用户。
- `require_admin()`：要求当前用户为管理员。
- `cleanup_expired_tokens()`：清理过期 Token。

`server/api.py` 的游客转存接口改为依赖 `get_current_user()`，不再从 `admin_api.py` 导入认证函数。

### 2. 管理 API 切换依赖

`server/admin_api.py` 移除本地认证函数，改为从 `server/auth.py` 导入认证依赖。

- 登录态检查和登出使用 `get_current_user()`。
- 用户管理、视频管理、导出、统计、Cookies 管理使用 `require_admin()`。
- 修改密码接口基于当前 `User` 判断本人或管理员。

### 3. 角色简化

后端：

- `CreateUserRequest` 和 `UpdateUserRequest` 只允许 `admin` / `user`。
- 网页接口仍禁止创建或提升管理员账号，管理员账号继续通过 `.env` 管理。
- 删除管理接口中的 `readonly` 权限分支。

前端：

- 删除 `readonly` 文案。
- 删除用户编辑弹窗中的「只读用户」选项。
- 删除基于 `readonly` 隐藏删除按钮的逻辑。
- 删除 `.role-badge.readonly` 样式。

## 验证记录

- `venv\Scripts\python.exe -m unittest tests.test_auth_roles_unittest -v`：通过，3 个测试通过。
- `venv\Scripts\python.exe -m unittest tests.test_v4_migrations_unittest -v`：通过，2 个测试通过。
- `venv\Scripts\python.exe -m compileall server`：通过。
- `node --check www\common.js`：通过。
- `node --check www\admin\js\render.js`：通过。
- `node --check www\admin\js\users.js`：通过。
- 安全边界轻量脚本：通过。

## 当前遗留

- `test_security_boundaries.py` 仍是 `pytest` 写法，当前虚拟环境缺少 `pytest`，本次继续用轻量脚本覆盖安全边界验证。
- 普通用户视频库、下载去重、容量限制和 `share_token` 播放仍属于任务 4。
- 邀请码接口仍属于任务 5。
