# GoTube V4.5.0 用户昵称与自助改密实现计划

> **面向 AI 代理的工作指引：** 按步骤执行，完成一组能力就做本地提交。跨数据库、认证边界或前后端契约的阶段完成后，补一份工作日志。不要推送远程仓库。

**目标：** 在不改动登录账号语义的前提下，为用户引入昵称字段，统一展示账号/昵称/ID，并为普通用户提供自助改密码能力。

**架构：** 后端新增一层用户资料规则与响应扩展，数据库为 `users` 表增加昵称字段；管理员端与下载页共同消费新的用户身份字段；密码修改能力拆成“普通用户本人自助改密”和“管理员维持现有重置他人密码”两条路径。

**技术栈：** FastAPI、SQLAlchemy、SQLite、原生前端 JS、unittest

---

## 文件结构

### 新增文件

- `server/user_profile.py`
  - 用户昵称归一化、昵称合法性校验、密码合法性校验、用户展示信息辅助函数。
- `tests/test_user_profile_unittest.py`
  - 昵称与密码规则的纯单元测试。
- `docs/superpowers/worklogs/2026-04-29-task-17-user-profile-backend.md`
  - 数据库迁移、接口边界与认证调整的工作日志。
- `docs/superpowers/worklogs/2026-04-29-task-18-user-profile-frontend.md`
  - 管理页、下载页与注册/改密交互调整的工作日志。

### 修改文件

- `server/db.py`
  - `User` 模型扩展昵称字段，`to_dict()` 补充 `display_name`。
- `server/migrations.py`
  - 为 `users` 表追加昵称列与索引，回填历史数据。
- `server/models.py`
  - 请求/响应模型新增 `display_name`、`UserIdentityResponse`、`UpdateProfileRequest` 等字段。
- `server/invites.py`
  - 注册时接收并校验昵称。
- `server/api.py`
  - 公开注册接口、`/me/profile`、`/me/password`、`/me/quota`、`/me/videos` 等接口响应扩展。
- `server/admin_api.py`
  - 登录校验返回、`/auth/check`、用户列表、创建/编辑用户、密码修改接口行为拆分与管理员本人改密保护。
- `server/auth.py`
  - Token payload 返回扩展后的用户展示信息。
- `www/download.html`
  - 注册表单新增昵称输入，个人资料/改密入口占位。
- `www/download.js`
  - 登录后身份固定显示账号/昵称/ID，注册提交昵称，新增普通用户修改昵称/密码流程。
- `www/admin/js/auth.js`
  - 管理端登录后用户摘要显示账号/昵称/ID。
- `www/admin/js/render.js`
  - 导航与媒体拥有者处展示账号/昵称/ID。
- `www/admin/js/users.js`
  - 用户列表新增昵称列与固定三元身份显示，新增编辑昵称，限制管理员本人改密入口。
- `www/admin/css/admin.css`
  - 新增昵称/账号/ID 组合显示样式、资料表单样式。
- `tests/test_v4_migrations_unittest.py`
  - 扩展迁移测试覆盖昵称列与回填。
- `tests/test_invites_unittest.py`
  - 注册新增昵称字段覆盖。
- `tests/test_auth_roles_unittest.py`
  - 响应模型和管理员同步昵称回填验证。
- `tests/test_admin_management_unittest.py`
  - 管理员用户接口与密码边界验证。
- `tests/test_admin_users_frontend_unittest.py`
  - 用户页文本与结构契约更新。
- `tests/test_frontend_session_contract_unittest.py`
  - 下载页身份信息与新入口契约更新。

## 任务 1：数据库与规则层

**文件：**
- 创建：`server/user_profile.py`
- 修改：`server/db.py`
- 修改：`server/migrations.py`
- 测试：`tests/test_user_profile_unittest.py`
- 测试：`tests/test_v4_migrations_unittest.py`

- [ ] **步骤 1：先写昵称与密码规则测试**

覆盖：
- 中日韩昵称通过
- 危险字符昵称拒绝
- 首尾空格清理与连续空格压缩
- 密码长度与全空格校验

- [ ] **步骤 2：实现 `server/user_profile.py`**

包含最少这些函数：
- `normalize_display_name(value: str) -> str`
- `validate_display_name(value: str) -> str`
- `validate_new_password(value: str) -> str`
- `build_user_identity(user) -> dict`

- [ ] **步骤 3：扩展 `User` 模型**

在 `server/db.py`：
- 给 `users` 增加 `display_name`
- 给 `users` 增加 `display_name_key`
- `to_dict()` 返回这两个字段

- [ ] **步骤 4：扩展迁移**

在 `server/migrations.py`：
- 检测并追加两个新列
- 历史用户回填 `display_name=username`
- 历史用户回填 `display_name_key=normalize_display_name(username)`
- 为 `display_name_key` 建普通索引

- [ ] **步骤 5：运行测试并提交**

运行：
```bash
python -m unittest tests.test_user_profile_unittest tests.test_v4_migrations_unittest
```

提交说明：
```bash
git add server/user_profile.py server/db.py server/migrations.py tests/test_user_profile_unittest.py tests/test_v4_migrations_unittest.py
git commit -m "feat(profile): 增加昵称字段与迁移"
```

- [ ] **步骤 6：补工作日志**

写入：
- `docs/superpowers/worklogs/2026-04-29-task-17-user-profile-backend.md`

记录：
- 新列设计
- 回填策略
- 为什么昵称不做唯一约束
- 为什么管理员本人密码不进入页面修改

## 任务 2：后端接口与认证边界

**文件：**
- 修改：`server/models.py`
- 修改：`server/invites.py`
- 修改：`server/api.py`
- 修改：`server/admin_api.py`
- 修改：`server/auth.py`
- 测试：`tests/test_invites_unittest.py`
- 测试：`tests/test_auth_roles_unittest.py`
- 测试：`tests/test_admin_management_unittest.py`

- [ ] **步骤 1：先扩请求/响应模型**

在 `server/models.py`：
- `UserResponse` 增加 `display_name`
- `CreateUserRequest` 增加 `display_name`
- `UpdateUserRequest` 增加 `display_name`
- `RegisterRequest` 增加 `display_name`
- 增加 `UpdateProfileRequest`

- [ ] **步骤 2：注册流程接入昵称**

在 `server/invites.py` 和 `server/api.py`：
- 注册时接收 `display_name`
- 使用 `validate_display_name`
- 创建普通用户时保存 `display_name` 与 `display_name_key`

- [ ] **步骤 3：用户资料与改密接口**

在 `server/api.py`：
- 新增 `PATCH /api/me/profile`
- 新增 `POST /api/me/password`
- 只允许普通用户走 `/api/me/password`
- 改密码成功后废掉该用户全部 token

- [ ] **步骤 4：管理端接口收口**

在 `server/admin_api.py`：
- 登录和 `/auth/check` 返回 `display_name`
- 创建/编辑用户支持昵称
- 用户列表/单用户资料返回昵称
- `/users/{user_id}/password` 保持管理员改别人密码
- 禁止管理员本人通过该接口改自己密码

- [ ] **步骤 5：认证 payload 扩展**

在 `server/auth.py`：
- `verify_token` 返回 `display_name`
- 兼容旧 token 逻辑

- [ ] **步骤 6：运行测试并提交**

运行：
```bash
python -m unittest tests.test_invites_unittest tests.test_auth_roles_unittest tests.test_admin_management_unittest
python -m py_compile server/api.py server/admin_api.py server/auth.py server/invites.py server/models.py server/user_profile.py
```

提交说明：
```bash
git add server/models.py server/invites.py server/api.py server/admin_api.py server/auth.py tests/test_invites_unittest.py tests/test_auth_roles_unittest.py tests/test_admin_management_unittest.py docs/superpowers/worklogs/2026-04-29-task-17-user-profile-backend.md
git commit -m "feat(profile): 扩展昵称与普通用户改密接口"
```

## 任务 3：下载页前端

**文件：**
- 修改：`www/download.html`
- 修改：`www/download.js`
- 测试：`tests/test_frontend_session_contract_unittest.py`

- [ ] **步骤 1：注册表单新增昵称字段**

在 `www/download.html`：
- 注册表单新增昵称输入
- 文案明确“昵称用于显示，不用于登录”

- [ ] **步骤 2：登录后身份固定显示三项**

在 `www/download.js`：
- 统一显示账号、昵称、ID
- 不再做按需隐藏

- [ ] **步骤 3：普通用户资料修改**

在 `www/download.js`：
- 新增修改昵称入口
- 新增普通用户修改密码入口
- 改密码成功后清理登录态并跳回登录入口
- 管理员不显示本人改密入口

- [ ] **步骤 4：更新前端契约测试并提交**

运行：
```bash
node --check www/download.js
python -m unittest tests.test_frontend_session_contract_unittest
```

提交说明：
```bash
git add www/download.html www/download.js tests/test_frontend_session_contract_unittest.py
git commit -m "feat(profile): 调整下载页昵称与自助改密"
```

## 任务 4：管理页前端

**文件：**
- 修改：`www/admin/js/auth.js`
- 修改：`www/admin/js/render.js`
- 修改：`www/admin/js/users.js`
- 修改：`www/admin/css/admin.css`
- 测试：`tests/test_admin_users_frontend_unittest.py`

- [ ] **步骤 1：管理页身份摘要显示三项**

在导航用户摘要与拥有者显示位置统一展示：
- 账号
- 昵称
- ID

- [ ] **步骤 2：用户列表增加昵称列**

保持：
- 第一列 `ID`
- 第二列 `账号`
- 第三列 `昵称`

同时更新搜索逻辑，支持：
- 数字 ID
- 账号
- 昵称
- 状态
- 角色

- [ ] **步骤 3：用户编辑与密码弹窗拆边界**

在 `www/admin/js/users.js`：
- 新增昵称输入
- 管理员用户可编辑昵称
- 管理员本人不显示“改自己密码”表单
- 管理员改普通用户密码继续保留

- [ ] **步骤 4：更新前端测试并提交**

运行：
```bash
node --check www/admin/js/auth.js
node --check www/admin/js/render.js
node --check www/admin/js/users.js
python -m unittest tests.test_admin_users_frontend_unittest
```

提交说明：
```bash
git add www/admin/js/auth.js www/admin/js/render.js www/admin/js/users.js www/admin/css/admin.css tests/test_admin_users_frontend_unittest.py
git commit -m "feat(profile): 调整管理页用户身份展示"
```

- [ ] **步骤 5：补工作日志**

写入：
- `docs/superpowers/worklogs/2026-04-29-task-18-user-profile-frontend.md`

记录：
- 下载页与管理页各自改了什么
- 为什么统一固定显示账号/昵称/ID
- 为什么管理员前端不提供本人改密入口

## 任务 5：总回归

**文件：**
- 修改：`docs/superpowers/worklogs/2026-04-29-task-18-user-profile-frontend.md`

- [ ] **步骤 1：运行回归检查**

运行：
```bash
python -m unittest tests.test_user_profile_unittest tests.test_v4_migrations_unittest tests.test_invites_unittest tests.test_auth_roles_unittest tests.test_admin_management_unittest tests.test_admin_users_frontend_unittest tests.test_frontend_session_contract_unittest
node --check www/download.js
node --check www/admin/js/auth.js
node --check www/admin/js/render.js
node --check www/admin/js/users.js
node build.js
git diff --check
```

- [ ] **步骤 2：本地收尾提交**

```bash
git add docs/superpowers/plans/2026-04-29-v4-5-user-profile.md docs/superpowers/worklogs/2026-04-29-task-18-user-profile-frontend.md
git commit -m "docs(plan): 完成 v4.5.0 实施记录"
```
