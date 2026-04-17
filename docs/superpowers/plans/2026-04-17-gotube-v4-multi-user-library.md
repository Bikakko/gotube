# GoTube v4 多用户视频库实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 将 GoTube 从单一视频库升级为多用户视频库，支持普通用户容量限制、管理员全局管理、邀请码注册，并修复 v3 已发现的安全隐患。

**架构：** 先集中安全边界，再引入数据库归属模型，最后调整 API 和前端。旧文件结构保持可读，新下载进入用户目录。数据库用 `media_assets` 表示物理文件，用 `user_video_items` 表示用户视频库条目。

**技术栈：** FastAPI、SQLAlchemy、SQLite、Pydantic、yt-dlp、原生 JavaScript。

---

## 文件结构

| 文件 | 操作 | 职责 |
| --- | --- | --- |
| `server/security.py` | 创建 | 输入校验、角色校验、hash 和 session 校验。 |
| `server/path_utils.py` | 创建 | 安全路径解析，防止路径穿越。 |
| `server/auth.py` | 创建 | 当前用户依赖、管理员依赖、Token 校验复用。 |
| `server/migrations.py` | 创建 | v4 数据库迁移和 schema version 管理。 |
| `server/video_library.py` | 创建 | 视频资产登记、查询、删除和 hash 查找。 |
| `server/quota.py` | 创建 | 用户容量计算和下载准入判断。 |
| `server/guest_sessions.py` | 创建 | 游客 session 校验、统计、转存和清理。 |
| `server/db.py` | 修改 | 新增 `MediaAsset`、`UserVideoItem`、`InviteCode`、`SchemaMigration` 和用户容量字段。 |
| `server/config.py` | 修改 | 新增普通用户默认容量配置。 |
| `server/models.py` | 修改 | 新增注册、邀请码、容量和视频响应模型。 |
| `server/api.py` | 修改 | 拆分公开 API 和登录用户 API，收紧危险接口。 |
| `server/admin_api.py` | 修改 | 管理员全局视频库、用户容量、邀请码管理。 |
| `server/downloader.py` | 修改 | 支持用户下载目录，删除直接信任 `session_id` 的路径拼接。 |
| `server/queue_manager.py` | 修改 | 任务绑定用户身份，`client_id` 只用于进度分发。 |
| `server/main.py` | 修改 | 分享播放完整 hash 匹配，WebSocket guest 清理走安全服务。 |
| `www/download.js` | 修改 | 修复 XSS，登录用户下载、容量展示、转存鉴权。 |
| `www/common.js` | 修改 | 删除 readonly 文案，补充新 API 工具方法。 |
| `www/admin/js/*.js` | 修改 | 用户容量、邀请码、全局视频库筛选。 |
| `www/admin/css/admin.css` | 修改 | 删除 readonly 样式，增加容量和邀请码 UI 样式。 |
| `.env.example` | 修改 | 新增 `GOTUBE_USER_STORAGE_QUOTA_MB`。 |

---

## 任务 1：安全边界基础

**文件：**
- 创建：`server/security.py`
- 创建：`server/path_utils.py`
- 修改：`server/downloader.py`
- 修改：`server/main.py`
- 修改：`server/api.py`
- 修改：`www/download.js`

- [ ] **步骤 1：创建输入校验模块**

新增 `server/security.py`：

```python
import re
from fastapi import HTTPException

GUEST_SESSION_RE = re.compile(r"^guest_[a-z0-9]+_[a-z0-9]{4,32}$")
HASH_ID_RE = re.compile(r"^[0-9a-f]{8}$")
VALID_ROLES = {"admin", "user"}


def validate_guest_session_id(session_id: str) -> str:
    if not session_id or not GUEST_SESSION_RE.fullmatch(session_id):
        raise HTTPException(status_code=400, detail="非法 session_id")
    return session_id


def validate_hash_id(hash_id: str) -> str:
    value = (hash_id or "").lower()
    if not HASH_ID_RE.fullmatch(value):
        raise HTTPException(status_code=400, detail="非法视频标识")
    return value


def normalize_role(role: str) -> str:
    if role == "readonly":
        return "user"
    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="非法角色")
    return role
```

- [ ] **步骤 2：创建安全路径解析模块**

新增 `server/path_utils.py`：

```python
from pathlib import Path
from fastapi import HTTPException


def resolve_inside(base_dir: Path, *parts: str | Path) -> Path:
    base = base_dir.resolve()
    target = base.joinpath(*parts).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="非法文件路径") from exc
    return target
```

- [ ] **步骤 3：修复 guest session 路径**

在 `downloader.py` 中，`cleanup_guest_session()`、`get_guest_download_count()`、`transfer_guest_session()` 不再使用 `self.guest_download_dir / session_id`，改为：

```python
from .security import validate_guest_session_id
from .path_utils import resolve_inside

session_id = validate_guest_session_id(session_id)
session_dir = resolve_inside(self.guest_download_dir, session_id)
```

删除前确认 `session_dir != self.guest_download_dir.resolve()`。

- [ ] **步骤 4：修复完整 hash 匹配**

在 `main.py` 和 `api.py` 中，对 `/watch`、`/api/video/{hash_id}/info`、`/api/thumbnail/{hash_id}` 使用 `validate_hash_id()`。查找逻辑只允许：

```python
hash_id = validate_hash_id(hash_id)
matched_file = hash_index.get(hash_id)
```

删除 `h.startswith(hash_id) or hash_id.startswith(h)`。

- [ ] **步骤 5：收紧公开下载管理接口**

临时处理策略：

- `DELETE /api/downloads/{filename:path}` 返回 `403` 或迁移到管理员接口。
- `/api/downloads` 如果前端没有游客依赖，改为要求登录。
- `/api/downloads/stream/{filename:path}` 不作为公开分享入口。任务 1 保留 legacy `/watch?v={hash}` 精确匹配，后续用户级分享改为 `/watch?v={share_token}`。

- [ ] **步骤 6：修复任务列表 XSS**

把 `download.js` 中 `renderTasks()` 的字符串拼接改为 DOM API。外部数据只通过 `textContent` 写入。

- [ ] **步骤 7：验证**

运行：

```powershell
python -m compileall server
```

手工验证：

- `session_id=../../x` 被拒绝。
- `/watch?v=a` 被拒绝。
- 恶意标题 `<img src=x onerror=alert(1)>` 在任务列表中按文本显示。

---

## 任务 2：数据库迁移基础

**文件：**
- 修改：`server/db.py`
- 创建：`server/migrations.py`
- 测试：`tests/test_v4_migrations_unittest.py`

- [x] **步骤 1：先写迁移测试**

使用标准库 `unittest` 覆盖：

- v4 表结构存在。
- `readonly` 用户迁移为 `user`。
- 旧视频登记到 `media_assets`。
- 重复迁移不重复登记。
- `temp_guest` 下的视频不登记。
- 文件不被移动或删除。

- [x] **步骤 2：扩展 User 表模型**

在 `User` 中新增：

```python
storage_quota_mb = Column(Integer, nullable=True)
storage_used_bytes = Column(Integer, nullable=False, default=0)
```

`to_dict()` 返回这两个字段。

- [x] **步骤 3：新增 MediaAsset 和 UserVideoItem 模型**

`MediaAsset` 表示硬盘上的物理视频文件，包含 `fingerprint`、`file_hash`、`filepath`、`size_bytes`、`meta_json` 等字段。

`UserVideoItem` 表示用户视频库条目，包含 `owner_user_id`、`media_asset_id`、`share_token`、`share_enabled`、`deleted_at` 等字段。唯一约束为：

```text
owner_user_id + media_asset_id
share_token
```

- [x] **步骤 4：新增 InviteCode 和 SchemaMigration 模型**

`InviteCode` 为后续邀请码注册预留表结构。`SchemaMigration` 记录 v4 迁移是否已执行。

- [x] **步骤 5：创建幂等迁移脚本**

新增 `server/migrations.py`，实现：

```python
def run_v4_migrations(engine: Engine, download_dir: Path) -> None:
    _ensure_schema(engine, conn)
    _migrate_readonly_users(conn)
    _index_legacy_media_assets(conn, download_dir)
    mark_version(conn, 4)
```

迁移时跳过：

- `temp_guest`
- `.temp_ytdlp`
- 非视频文件
- 符号链接视频文件

legacy 视频登记到 `media_assets`，不创建 `user_video_items`。

- [x] **步骤 6：启动时执行迁移**

`init_db()` 在 `Base.metadata.create_all()` 后执行 `run_v4_migrations()`。旧库通过 `ALTER TABLE` 补用户容量列，新库直接由 ORM 建表。

- [x] **步骤 7：验证**

运行：

```powershell
venv\Scripts\python.exe -m unittest tests.test_v4_migrations_unittest -v
venv\Scripts\python.exe -m compileall server
venv\Scripts\python.exe -c "from server.main import app; print(app.title)"
```

确认：

- 新表存在。
- `readonly` 用户被改为 `user`。
- 旧视频被索引到 `media_assets`，但文件没有被移动。
- `user_video_items` 在迁移阶段保持为空，后续任务 4 再创建用户视频库条目。

---

## 任务 3：认证上下文与角色简化

**文件：**
- 创建：`server/auth.py`
- 修改：`server/admin_api.py`
- 修改：`server/api.py`
- 修改：`server/models.py`
- 修改：`www/admin/js/users.js`
- 修改：`www/admin/js/render.js`
- 修改：`www/common.js`

- [ ] **步骤 1：抽取认证依赖**

新增 `server/auth.py`，从 `admin_api.py` 迁移通用逻辑：

```python
async def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    ...


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="权限不足")
    return user
```

- [ ] **步骤 2：管理员 API 使用 require_admin**

把用户管理、邀请码管理、全局视频管理接口统一改为 `Depends(require_admin)`。

- [ ] **步骤 3：普通用户 API 使用 get_current_user**

登录用户接口不再信任 `client_id` 判权。`client_id` 只保留给任务查询和 WebSocket 进度。

- [ ] **步骤 4：删除 readonly 角色**

后端：

- 创建用户时只允许 `admin` 和 `user`。
- 修改用户时只允许 `admin` 和 `user`。
- 删除 `payload["role"] == "readonly"` 分支。

前端：

- 删除 readonly 下拉选项。
- 删除 readonly 禁用删除按钮的逻辑。
- 删除 readonly 文案和样式。

- [ ] **步骤 5：验证**

运行：

```powershell
python -m compileall server
```

手工验证：

- 普通用户无法进入用户管理。
- 管理员可创建普通用户。
- 前端不再出现 readonly。

---

## 任务 4：视频库服务与容量控制

**文件：**
- 创建：`server/video_library.py`
- 创建：`server/quota.py`
- 修改：`server/downloader.py`
- 修改：`server/queue_manager.py`
- 修改：`server/api.py`
- 修改：`server/admin_api.py`
- 修改：`server/config.py`
- 修改：`.env.example`

- [ ] **步骤 1：新增默认容量配置**

在 `config.py` 中读取：

```python
_user_storage_quota_mb: int = _i(
    "GOTUBE_USER_STORAGE_QUOTA_MB",
    required=False,
    default=10240,
    min_val=0,
)
```

在 settings 中暴露：

```python
@property
def user_storage_quota_mb(self) -> int:
    return _user_storage_quota_mb
```

- [ ] **步骤 2：创建 quota.py**

实现：

```python
def get_effective_quota_bytes(user: User) -> int | None:
    if user.role == "admin":
        return None
    quota_mb = user.storage_quota_mb
    if quota_mb is None:
        quota_mb = settings.user_storage_quota_mb
    if quota_mb <= 0:
        return 0
    return quota_mb * 1024 * 1024


def ensure_user_can_download(user: User) -> None:
    quota = get_effective_quota_bytes(user)
    if quota is not None and user.storage_used_bytes >= quota:
        raise HTTPException(status_code=403, detail="用户容量已满")
```

- [ ] **步骤 3：创建 video_library.py**

实现：

```python
def register_user_video_item(session: Session, task: DownloadTask, owner_user_id: int) -> UserVideoItem:
    ...


def list_visible_videos(session: Session, user: User, owner_user_id: int | None = None) -> list[UserVideoItem]:
    ...


def delete_visible_video(session: Session, user: User, video_id: int) -> list[str]:
    ...
```

`register_user_video_item()` 先按内容指纹查找或创建 `MediaAsset`，再为当前用户创建 `UserVideoItem`。普通用户只能查询和删除自己的视频库条目。管理员可按 `owner_user_id` 筛选，也可查看 legacy `MediaAsset`。

- [ ] **步骤 4：登录用户下载登记归属**

`POST /api/tasks` 获取当前用户：

- guest 请求没有 token 时保持临时下载。
- 登录用户请求带 token 时下载到用户目录。
- 任务完成后写入或复用 `media_assets`，并创建当前用户的 `user_video_items`。
- 如果同一指纹视频已存在，不重复下载物理文件；当前用户仍得到自己的视频库条目、分享 token 和管理能力。

`DownloadTask` 增加：

```python
owner_user_id: int | None = None
```

- [ ] **步骤 5：用户目录落地**

新登录用户下载进入：

```text
downloads/users/{user_id}/{title}_{hash}/{hash}.mp4
```

legacy 文件保持原位置。

- [ ] **步骤 6：容量统计更新**

下载完成登记后：

```python
user.storage_used_bytes = calculate_user_usage(session, user.id)
session.commit()
```

删除视频后同样刷新容量。删除逻辑先软删除用户自己的 `user_video_items`，只有没有任何活跃条目引用对应 `media_assets` 时才物理删除文件。

- [ ] **步骤 7：验证**

手工验证：

- 普通用户下载后文件进入 `downloads/users/{id}`。
- 普通用户只看到自己的视频。
- 管理员看到所有视频。
- 普通用户超容量后新增下载返回 403。
- 管理员不受容量限制。

---

## 任务 5：邀请码注册

**文件：**
- 修改：`server/models.py`
- 修改：`server/api.py`
- 修改：`server/admin_api.py`
- 修改：`www/download.js`
- 修改：`www/index.html`
- 修改：`www/admin/js/render.js`

- [ ] **步骤 1：新增请求模型**

在 `models.py` 中新增：

```python
class RegisterRequest(BaseModel):
    username: str
    password: str
    invite_code: str


class CreateInviteRequest(BaseModel):
    max_uses: int = 1
    expires_hours: int | None = None
```

- [ ] **步骤 2：管理员生成邀请码**

在 `admin_api.py` 新增：

```python
@router.post("/invites")
async def create_invite(
    body: CreateInviteRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    ...
```

明文邀请码使用 `secrets.token_urlsafe(16)` 生成，数据库只保存 hash。

- [ ] **步骤 3：邀请码列表和作废**

新增：

```text
GET /invites
DELETE /invites/{id}
```

删除接口只把 `is_active` 设为 `False`。

- [ ] **步骤 4：公开注册接口**

在 `api.py` 新增：

```python
@router.post("/auth/register")
async def register(body: RegisterRequest, db: Session = Depends(get_db)):
    ...
```

注册成功创建 `role=user`，并增加邀请码 `used_count`。

- [ ] **步骤 5：前端注册入口**

下载页或登录页增加注册表单：

- 用户名
- 密码
- 邀请码

注册成功后提示用户登录。

- [ ] **步骤 6：验证**

手工验证：

- 管理员能生成邀请码。
- 明文邀请码只返回一次。
- 邀请码可注册普通用户。
- 用完次数后不能继续注册。
- 禁用邀请码不能注册。

---

## 任务 6：管理员多用户视频库界面

**文件：**
- 修改：`server/admin_api.py`
- 修改：`www/admin/js/data.js`
- 修改：`www/admin/js/render.js`
- 修改：`www/admin/js/users.js`
- 修改：`www/admin/js/events.js`
- 修改：`www/admin/css/admin.css`

- [ ] **步骤 1：全局视频列表支持 owner 筛选**

管理员视频接口支持：

```text
GET /videos?owner_user_id=12
GET /videos?owner=legacy
GET /videos
```

响应增加：

```json
{
  "owner_user_id": 12,
  "owner_username": "alice"
}
```

- [ ] **步骤 2：后台增加用户筛选器**

视频列表顶部增加：

- 全部
- Legacy
- 指定用户

- [ ] **步骤 3：用户管理展示容量**

用户表增加：

- 已用容量
- 容量上限
- 视频数量

编辑用户时可设置 `storage_quota_mb`。

- [ ] **步骤 4：邀请码管理入口**

管理员导航栏增加「邀请码」入口，支持：

- 生成邀请码
- 查看邀请码列表
- 作废邀请码

- [ ] **步骤 5：验证**

手工验证：

- 管理员能按用户筛选视频。
- 管理员能看到 legacy 视频。
- 用户容量设置保存后生效。
- 邀请码管理 UI 可用。

---

## 任务 7：用户下载页适配 v4

**文件：**
- 修改：`www/download.js`
- 修改：`www/download.html`
- 修改：`server/api.py`

- [ ] **步骤 1：登录态请求带 Token**

下载页提交任务时，如果已登录，则带：

```javascript
headers.Authorization = `Bearer ${token}`;
```

后端据此识别当前用户，不再依赖前端不传 `session_id` 来判断是否登录。

- [ ] **步骤 2：显示容量状态**

新增接口：

```text
GET /api/me/quota
```

下载页显示：

```text
已用 1.2 GB / 10 GB
```

- [ ] **步骤 3：游客转存带 Token**

登录成功后调用：

```javascript
fetch(`/api/guest-downloads/${guestSessionId}/transfer?client_id=${clientId}`, {
  method: 'POST',
  headers: { Authorization: `Bearer ${token}` },
});
```

- [ ] **步骤 4：验证**

手工验证：

- 游客下载仍可用。
- 登录后下载进入用户库。
- 登录后游客视频转存到当前用户库。
- 容量超限时 UI 显示后端错误。

---

## 任务 8：最终验证和版本升级

**文件：**
- 修改：`VERSION`
- 修改：`server/main.py`
- 修改：`.env.example`
- 可选修改：`README.md`

- [ ] **步骤 1：版本号升级**

将版本升级为 `4.0.0`。

- [ ] **步骤 2：补充环境变量说明**

`.env.example` 增加：

```dotenv
# 普通用户默认视频库容量，单位 MB。0 表示普通用户不能下载，管理员不受限制。
GOTUBE_USER_STORAGE_QUOTA_MB=10240
```

- [ ] **步骤 3：运行后端验证**

运行：

```powershell
python -m compileall server
```

如果项目已有测试：

```powershell
pytest
```

- [ ] **步骤 4：手工回归清单**

检查：

- 管理员登录。
- 管理员创建普通用户。
- 管理员生成邀请码。
- 邀请码注册普通用户。
- 普通用户下载视频。
- 普通用户只能看到自己的视频。
- 管理员能看到所有视频。
- 容量限制生效。
- 旧视频仍可在管理员后台看到。
- 分享链接播放正常。
- 游客下载和登录转存正常。
- 危险路径和短 hash 被拒绝。

- [ ] **步骤 5：提交**

```powershell
git add .
git commit -m "feat: 升级 v4 多用户视频库"
```

---

## 风险和回滚

### 主要风险

- 迁移脚本误登记或重复登记 legacy 视频。
- 普通用户下载路径变更影响分享播放。
- 前端仍有遗漏的 `readonly` 判断。
- 游客转存加鉴权后，旧前端流程需要同步修改。
- 容量统计缓存和实际文件大小不一致。

### 回滚策略

- v4 不强制移动旧视频文件，因此文件层面可回滚。
- 数据库迁移只新增表和列，避免删除历史字段。
- `readonly` 迁移为 `user` 属于行为变更，回滚前需要确认是否要恢复角色。
- 如果用户目录下载出现问题，可临时把登录用户下载目录切回旧目录，但仍保留 `MediaAsset` 和 `UserVideoItem` 记录归属。

## 执行建议

按任务顺序小步提交。任务 1 是安全前置项，不能跳过。任务 2 到任务 4 是 v4 的核心后端能力，完成后再做邀请码和后台 UI。每个任务完成后至少运行 `python -m compileall server`，涉及前端的任务需要手工回归主要页面。
