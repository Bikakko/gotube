# 任务 17 工作日志：V4.5.0 后端用户昵称与自助改密

日期：2026-04-29

## 本次完成

- 为 `users` 表增加 `display_name`、`display_name_key`
- 在迁移流程中加入 v5 回填逻辑，历史用户默认 `display_name = username`
- 新增 `server/user_profile.py`，集中处理昵称合法性、密码合法性和统一身份序列化
- 注册流程支持提交昵称
- 管理员登录态响应、鉴权载荷支持返回昵称
- 新增普通用户接口：
  - `PATCH /api/me/profile`
  - `POST /api/me/password`
- 保留管理员重置普通用户密码能力
- 明确禁止管理员本人通过页面改密码，继续由 `.env` 管理

## 设计决策

### 1. 昵称不做唯一约束

昵称不参与登录、鉴权、权限判断，也不作为资源归属键。把昵称做成唯一只会提高维护成本，并制造无意义冲突。因此只保留：

- 合法字符校验
- 空白归一化
- 安全字符限制

`display_name_key` 仍然保留，当前主要用于：

- 统一归一化
- 后续前端搜索/排序扩展

而不是唯一约束。

### 2. 管理员密码不进入页面自助修改

当前管理员账号由 `.env` 同步写入数据库。若允许管理员本人在页面改密码，重启后又会被 `.env` 覆盖，形成伪能力。这里直接收口：

- 管理员昵称可改
- 管理员本人密码不可在页面改
- 管理员密码继续通过部署配置维护

### 3. 普通用户改密码后强制重新登录

自助改密码成功后，直接废掉该用户全部有效 token。这样边界最清晰：

- 不保留旧会话
- 不区分当前设备和其他设备
- 不引入额外会话管理复杂度

## 修复的边角问题

- 管理员重置普通用户密码时，兼容历史异常哈希，不因 `Invalid salt` 中断
- 管理页时间筛选对无时区时间统一按 UTC 入库时间解释，再转换到本地时区，避免“今天”过滤误伤

## 验证

执行：

```powershell
venv\Scripts\python.exe -m py_compile server\api.py server\admin_api.py server\auth.py server\invites.py server\migrations.py server\models.py server\user_profile.py
venv\Scripts\python.exe -m unittest tests.test_user_profile_unittest tests.test_v4_migrations_unittest tests.test_invites_unittest tests.test_auth_roles_unittest tests.test_admin_management_unittest
```

结果：

- `py_compile` 通过
- `36` 项后端相关测试通过
