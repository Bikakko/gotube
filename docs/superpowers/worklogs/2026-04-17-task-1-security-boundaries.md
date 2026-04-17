# GoTube v4 任务 1 工作日志：安全边界基础

## 基本信息

- **日期：** 2026-04-17
- **范围：** 任务 1：安全边界基础
- **目标：** 在不改变现有数据结构的前提下，先修复已知高风险边界问题，为后续 v4 多用户视频库改造打底。

## 已处理问题

### 1. Guest Session 路径边界

- 新增 `server/security.py`，集中校验外部传入的 `session_id` 和分享 `hash_id`。
- 新增 `server/path_utils.py`，提供 `resolve_inside()`，统一处理「拼路径后必须仍在根目录内」的边界检查。
- 下载器中涉及 guest session 的清理、统计、转存、后处理路径，统一改为先校验 `session_id`，再做目录边界确认。
- 删除 guest session 前增加根目录保护，避免误删 `temp_guest` 根目录。

### 2. 公开视频管理 API 收口

- `/api/downloads` 不再公开返回完整视频库列表。
- `/api/downloads/stream/{filename:path}` 不再公开按文件名播放主视频库内容。
- `/api/downloads/{filename:path}` 不再公开按文件名删除主视频库内容。
- 管理类能力保留在现有管理员接口中，公开播放路径收敛到 `/watch?v={hash}`。

### 3. 前端任务列表 XSS

- `www/download.js` 的任务列表渲染从 `innerHTML` 字符串拼接改为 DOM API。
- 标题、错误信息、状态信息统一走 `textContent`。
- 动态操作按钮改为 `addEventListener`，不再拼接动态 `onclick` 属性。

### 4. 分享 Hash 精确匹配

- `/watch?v=...`、`/api/video/{hash_id}/info`、`/api/video/{hash_id}/thumbnail` 改为要求完整 8 位 hex。
- 移除短前缀匹配和递归文件名前缀扫描，避免枚举成本过低和前缀误命中。

### 5. 游客转存接口鉴权

- `/api/guest-downloads/{session_id}/transfer` 增加 Bearer token 校验。
- 前端登录后调用游客转存时会带上现有 `gotube_admin_token`。

## 新增文件

- `server/security.py`
- `server/path_utils.py`
- `tests/test_security_boundaries.py`

## 验证记录

- `venv\Scripts\python.exe -m compileall server`：通过。
- `venv\Scripts\python.exe -c "from server.main import app; print(app.title)"`：通过，输出 `GoTube`。
- `node --check www\download.js`：通过。
- 安全边界轻量脚本：通过，覆盖非法 `session_id`、短 hash、非 hex hash、目录穿越。
- 本地启动检查：通过。使用临时端口启动 `uvicorn server.main:app`，主页返回 200，下载页返回 200，`/api/downloads` 返回 403，`/watch?v=a` 返回 400。
- `venv\Scripts\python.exe -m pytest tests\test_security_boundaries.py -q`：未运行成功，当前虚拟环境未安装 `pytest`。

## 当前遗留

- 本次只是安全边界基础，不包含 v4 多用户视频库、容量限制、邀请码注册、角色删减等主体改造。
- `tests/test_security_boundaries.py` 已写入，但需要后续补齐测试依赖或开发依赖安装流程后才能用 `pytest` 直接执行。
- 公开接口已收口，后续任务应继续把鉴权依赖从 `admin_api.py` 中抽到独立 `auth` 模块，降低 API 层耦合。
