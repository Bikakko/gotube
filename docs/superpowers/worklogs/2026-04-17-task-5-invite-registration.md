# 2026-04-17 任务 5：邀请码注册

## 背景

本阶段为 v4 增加邀请码注册机制。用户确认不需要服务端 pepper；用户名和密码只做基础门槛校验，不要求高强度。

## 本次实现

### 邀请码服务

新增 `server/invites.py`：

- `generate_invite_code()`：生成明文邀请码。
- `hash_invite_code()`：使用 SHA-256 保存邀请码 hash，不保存明文。
- `create_invite()`：管理员创建邀请码，明文 code 只在创建响应返回一次。
- `list_invites()`：列出邀请码元数据，不返回明文 code。
- `revoke_invite()`：作废邀请码。
- `consume_invite()`：校验并消费邀请码使用次数。
- `register_user_with_invite()`：用邀请码注册普通用户。

### 校验规则

- 用户名：`3-32` 位，允许字母、数字、下划线、短横线。
- 密码：至少 `6` 位。
- 邀请码必须：
  - 存在；
  - 未作废；
  - 未过期；
  - 未达到 `max_uses`。

注册成功后创建 `role=user`、`is_active=True` 的普通用户，并增加邀请码 `used_count`。

### API

管理员 API：

- `POST /{hidden_path}/admin/api/invites`
- `GET /{hidden_path}/admin/api/invites`
- `DELETE /{hidden_path}/admin/api/invites/{invite_id}`

公开 API：

- `POST /api/auth/register`

### 前端

在下载页登录弹窗中增加最小注册入口：

- 登录 / 注册切换；
- 用户名；
- 密码；
- 邀请码；
- 注册成功后回到登录面板，并提示用户登录。

完整后台邀请码管理 UI 暂留到后续任务六处理。

## 测试

新增 `tests/test_invites_unittest.py`，覆盖：

- 创建邀请码只保存 hash，不保存明文。
- 有效邀请码可注册普通用户。
- `max_uses` 用完后不可继续注册。
- 作废邀请码不可注册。
- 过期邀请码不可注册。
- 重复用户名不可注册。
- 用户名和密码基础校验。

## 验证记录

- `venv\Scripts\python.exe -m unittest tests.test_invites_unittest -v`
- `venv\Scripts\python.exe -m unittest tests.test_invites_unittest tests.test_auth_roles_unittest tests.test_v4_migrations_unittest tests.test_video_library_unittest -v`
- `venv\Scripts\python.exe -m compileall server`
- `node --check www\download.js`
- `git diff --check`
- 临时 `uvicorn server.main:app --port 8766` 启动检查：
  - `/health` 返回 200
  - `/{hidden_path}/admin/api/invites` 未授权返回 401
  - `/api/auth/register` 非法输入返回 422

备注：全量 `unittest discover` 仍会被既有 `tests/test_security_boundaries.py` 阻断，因为当前环境未安装 `pytest`。
