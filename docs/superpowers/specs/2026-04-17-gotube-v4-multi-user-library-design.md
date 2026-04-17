# GoTube v4 多用户视频库设计规格

## 背景

GoTube v3 已经具备管理员登录、普通用户管理、游客临时下载、下载队列、分享播放和后台视频管理能力。当前系统仍以单一下载目录作为全局视频库，普通用户与管理员在视频归属、容量控制和注册入口上缺少清晰边界。

v4 升级的重点是把系统从「单库下载工具」升级为「多用户视频库」。这次升级同时处理已发现的安全隐患，避免把旧的路径、鉴权和前端渲染风险扩散到新的多用户模型中。

## 目标

- 普通用户拥有独立视频库，只能查看和管理自己的视频。
- 管理员拥有全局视角，可查看、筛选和管理所有用户的视频库。
- 普通用户受容量限制，默认容量由环境变量配置，单个用户可单独覆盖。
- 管理员不受容量限制。
- 角色模型简化为 `admin` 和 `user`，删除 `readonly` 角色。
- 注册改为邀请码机制，邀请码只能由管理员生成。
- 兼容当前下载目录和 `meta.json` 数据，不强制移动历史文件。
- 修复 v3 中的路径穿越、公开管理 API、前端 XSS、短 hash 枚举和游客转存鉴权问题。

## 非目标

- 不在 v4 第一阶段引入复杂的团队、分组或共享空间。
- 不强制迁移现有视频文件到新目录。
- 不改变 `yt-dlp` 下载核心流程，除非是为了接入用户归属和容量校验。
- 不把邀请码设计成外部营销系统，只提供本地管理员生成和作废能力。
- 不在第一版实现细粒度 ACL，例如单个视频授权给指定用户。

## 当前问题

### 安全边界不集中

`session_id`、`filename`、`hash_id` 等来自客户端的参数在多个文件中直接参与路径拼接或文件查找。后续多用户化会增加路径数量，如果不先集中校验规则，问题会更难排查。

### 权限模型依赖接口习惯

部分公开视频接口同时承担管理能力，例如 `/api/downloads` 和 `DELETE /api/downloads/{filename}`。v4 需要明确区分公开能力、登录用户能力和管理员能力。

### 视频归属缺失

当前视频主要靠目录和 `meta.json` 表示，缺少数据库层面的所有者字段。管理员后台扫描全局目录，普通用户无法拥有独立视图。

### 容量无法按用户控制

当前仅有单视频大小限制 `GOTUBE_MAX_VIDEO_SIZE_MB`，没有用户总容量限制。

### 注册入口缺失

当前用户创建依赖管理员后台，普通用户无法通过受控方式自助注册。

## 目标架构

v4 使用「数据库记录归属，文件系统保留兼容」的方式演进。

```text
FastAPI 路由层
  ├─ 公开 API：登录、注册、分享播放
  ├─ 用户 API：我的视频、我的容量、我的下载任务
  └─ 管理 API：用户管理、邀请码、全局视频库

服务层
  ├─ auth.py：当前用户、角色校验
  ├─ security.py：session_id、hash_id、角色和输入校验
  ├─ path_utils.py：安全路径解析
  ├─ video_library.py：视频库查询、登记、删除、归属判断
  ├─ quota.py：容量统计和限制
  └─ guest_sessions.py：游客临时视频转存和清理

底层能力
  ├─ downloader.py：下载、后处理、元数据写入
  ├─ queue_manager.py：队列和 WebSocket 进度
  └─ db.py：用户、Token、视频资产、邀请码和迁移状态
```

路由层只负责 HTTP 参数、状态码和依赖注入。业务判断放到服务层，文件系统边界统一放到 `path_utils.py`。

## 数据模型

### 用户表扩展

`users` 表保留现有字段，新增：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `storage_quota_mb` | integer, nullable | 用户独立容量上限。为空时使用默认配置。管理员忽略该字段。 |
| `storage_used_bytes` | integer | 当前已用容量缓存。可通过扫描修复。 |

角色只允许：

- `admin`
- `user`

历史 `readonly` 用户迁移为 `user`，避免误删账号。

### 物理视频资产表

新增 `media_assets` 表，用于记录硬盘上真实存在的一份视频文件。该表不直接表示用户归属。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 主键。 |
| `fingerprint` | string | 内容指纹，作为跨用户去重依据。 |
| `file_hash` | string | 当前 8 位 CRC32 hash。 |
| `filename` | text | 相对下载目录的展示路径。 |
| `filepath` | text | 绝对路径或可解析路径。 |
| `size_bytes` | integer | 文件大小，单位字节。 |
| `title` | text | 视频标题。 |
| `source_url` | text | 原始下载 URL。 |
| `thumbnail` | text | 缩略图路径或 URL。 |
| `duration` | integer | 视频时长，单位秒。 |
| `meta_json` | text | 原始元数据 JSON。 |
| `created_at` | datetime | 记录创建时间。 |
| `last_seen_at` | datetime | 最近一次扫描或引用时间。 |

### 用户视频库条目表

新增 `user_video_items` 表，用于记录某个用户的视频库中拥有或引用了哪个物理视频资产。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 主键。 |
| `owner_user_id` | integer | 所属用户。 |
| `media_asset_id` | integer | 引用的物理视频资产。 |
| `display_title` | text | 用户侧显示标题。 |
| `share_token` | string | 用户级分享令牌，随机生成，不使用文件 hash。 |
| `share_enabled` | boolean | 是否允许分享。 |
| `created_from` | string | 来源：`download`、`guest_transfer` 或 `legacy_assign`。 |
| `saved_at` | datetime | 加入用户视频库时间。 |
| `deleted_at` | datetime, nullable | 软删除时间。 |

兼容和去重规则：

- 旧视频只登记到 `media_assets`，不自动归属普通用户。
- 新登录用户下载时先按 `fingerprint` 查找 `media_assets`。已存在则复用物理文件，只创建用户视频库条目。
- 用户删除视频时先删除自己的 `user_video_items` 条目。只有没有任何活跃用户条目引用该 `media_asset` 时，后续删除流程才允许物理删除文件。
- 分享链接绑定 `user_video_items.share_token`，并根据条目、用户和物理文件状态判断是否有效。

### 邀请码表

新增 `invite_codes` 表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 主键。 |
| `code_hash` | string | 邀请码 hash，不保存明文。 |
| `created_by_user_id` | integer | 创建邀请码的管理员 ID。 |
| `max_uses` | integer | 最大使用次数。 |
| `used_count` | integer | 已使用次数。 |
| `expires_at` | datetime, nullable | 过期时间。 |
| `is_active` | boolean | 是否有效。 |
| `created_at` | datetime | 创建时间。 |

邀请码明文只在生成时返回一次。

### 迁移表

新增 `schema_migrations` 表，记录当前 schema 版本。v4 迁移需要幂等，重复运行不能重复插入同一视频资产。

## 存储布局

当前目录保持可读：

```text
downloads/
  title_hash/
    hash.mp4
    meta.json
    thumbnail.jpg
  temp_guest/
    session_id/
      title_hash/
        hash.mp4
```

v4 不在文件路径中表达用户归属。第一阶段继续使用全局物理视频目录，后续如需整理存储，可演进为内容寻址目录：

```text
downloads/
  media/
    <fingerprint-or-media-id>/
      video.mp4
      meta.json
      thumbnail.jpg
  temp_guest/
    session_id/
      title_hash/
        hash.mp4
```

用户归属、删除权限和分享有效性统一由数据库 `user_video_items` 判断。旧文件不自动移动。管理员后台可显示 legacy 视频，并在后续版本提供「分配给用户」或「迁移到内容寻址目录」的显式操作。

## 权限模型

### 公开接口

公开接口不读取任意文件名，不提供管理能力。

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/video/{hash_id}/info`
- `GET /watch?v={hash_id}`

`hash_id` 必须是完整 8 位 hex 字符串。

### 登录用户接口

登录用户只能操作自己的数据。

- `GET /api/me`
- `GET /api/me/videos`
- `GET /api/me/quota`
- `POST /api/tasks`
- `GET /api/tasks`
- `DELETE /api/videos/{video_id}`
- `POST /api/guest-downloads/{session_id}/transfer`

`client_id` 只用于 WebSocket 进度分发，不再作为权限依据。

### 管理员接口

管理员接口继续挂在隐藏路径下。

- `GET /{hidden_path}/admin/api/users`
- `PUT /{hidden_path}/admin/api/users/{id}`
- `GET /{hidden_path}/admin/api/videos`
- `DELETE /{hidden_path}/admin/api/videos/{video_id}`
- `POST /{hidden_path}/admin/api/invites`
- `GET /{hidden_path}/admin/api/invites`
- `DELETE /{hidden_path}/admin/api/invites/{id}`

管理员能筛选：

- 全部视频
- 指定用户视频
- legacy/system 视频
- 自己的视频

## 容量规则

新增配置：

```dotenv
GOTUBE_USER_STORAGE_QUOTA_MB=10240
```

规则：

- 普通用户默认使用 `GOTUBE_USER_STORAGE_QUOTA_MB`。
- `users.storage_quota_mb` 不为空时覆盖默认值。
- 管理员没有容量限制。
- `storage_used_bytes` 可缓存，也可通过当前用户活跃的 `user_video_items` 关联 `media_assets` 修复。
- 下载完成后登记视频并更新容量。

下载前容量判断：

- 如果用户已超额，拒绝新增下载。
- 如果可以预估文件大小，预估后超额则拒绝。
- 如果无法预估，允许下载完成后登记；若完成后超额，保留本次视频，但禁止后续下载。

该策略优先保护用户数据，避免下载成功后立即删除造成体验问题。

## 邀请码注册

注册流程：

1. 管理员生成邀请码。
2. 系统返回明文邀请码一次。
3. 用户提交用户名、密码和邀请码。
4. 后端校验邀请码状态、过期时间和使用次数。
5. 创建 `role=user` 的普通账号。
6. 邀请码 `used_count += 1`。

安全约束：

- 邀请码明文不入库。
- 邀请码不能注册管理员。
- 用户名保持唯一。
- 被禁用邀请码不可使用。
- 超过使用次数的邀请码不可使用。

## 安全修复要求

v4 实施前必须先修复以下问题：

1. `session_id` 必须固定格式，所有 guest 路径必须限制在 `temp_guest` 内。
2. `/api/downloads` 和公开删除接口必须拆分或加鉴权。
3. `download.js` 不能把视频标题、错误信息直接拼到 `innerHTML`。
4. 旧分享 hash 必须完整匹配，不允许短前缀命中；新分享链接使用随机 `share_token`，并绑定用户视频库条目。
5. 游客转存必须要求登录用户，转存目标为当前用户的视频库。

## 前端变化

### 下载页

- 登录后下载进入当前用户视频库。
- 游客下载仍进入临时目录。
- 登录成功后转存游客视频时必须带 Bearer Token。
- 任务列表使用 DOM API 和 `textContent` 渲染外部数据。
- 显示当前用户容量状态。

### 管理后台

- 用户列表删除 `readonly` 角色。
- 用户列表展示容量上限和已用容量。
- 管理员可编辑普通用户容量。
- 视频列表增加用户筛选。
- 新增邀请码管理入口。

## 迁移策略

迁移必须可重复执行。

步骤：

1. 创建 `schema_migrations`、`media_assets`、`user_video_items`、`invite_codes`。
2. 给 `users` 增加容量字段。
3. 将历史 `readonly` 用户改为 `user`。
4. 扫描旧下载目录，写入 legacy 视频资产。
5. 跳过 `temp_guest`、`.temp_ytdlp` 和非视频文件。
6. 设置 schema version 为 `4`。

legacy 视频只登记为 `media_assets`。管理员后台可查看，普通用户不可见，除非后续通过显式分配创建 `user_video_items`。

## 验收标准

- 后端通过 `python -m compileall server`。
- 普通用户只能看到自己的视频。
- 管理员能看到所有用户视频和 legacy 视频。
- 普通用户不能删除他人视频。
- 管理员不受容量限制。
- 普通用户超容量后不能新增下载。
- 邀请码能注册普通用户，不能注册管理员。
- 邀请码过期、禁用或超次数后不能使用。
- 历史 `readonly` 用户迁移为 `user`。
- 旧视频不移动也能在管理员后台显示。
- `session_id=../../x` 被拒绝。
- `hash_id=a` 被拒绝，完整 8 位 hex hash 才允许访问。
- 下载页渲染恶意视频标题时不执行脚本。
