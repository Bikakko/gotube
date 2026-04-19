# GoTube V4.0.0 发布硬化实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在 V4.0.0 合并回 `master` 前，修复任务 10 验收后留下的发布级风险，并把管理后台、Cookie 诊断、URL 复用和发布巡检收敛到可维护状态。

**架构：** 不再扩展多用户视频库核心模型，优先做“发布硬化”：修正后台展示和筛选、增加非敏感 Cookie 诊断、增强 URL 规范化、补齐运维与迁移检查。每个任务应独立可测、独立提交，避免把后台大修和下载器核心逻辑混在同一个提交里。

**技术栈：** FastAPI、SQLAlchemy、SQLite、yt-dlp、原生 JavaScript、unittest、Node.js 语法检查。

---

## 文件结构

| 文件 | 操作 | 职责 |
| --- | --- | --- |
| `server/admin_api.py` | 修改 | 管理后台全局媒体聚合、时间筛选、Cookie 状态诊断 API |
| `server/video_library.py` | 修改 | 增加全局媒体聚合查询与维护删除结果统计 |
| `server/cookie_store.py` | 修改 | 提供 Cookie 关键字段诊断能力，不暴露敏感值 |
| `server/url_normalizer.py` | 创建 | 统一 URL 规范化、去播放进度、去跟踪参数、提取稳定媒体标识 |
| `server/downloader.py` | 修改 | 使用 URL 规范化结果登记来源，保留原始 URL 用于审计 |
| `server/api.py` | 修改 | 下载提交前使用规范化 URL 进行复用检查 |
| `www/admin/js/render.js` | 修改 | 管理后台全局媒体列表聚合展示 |
| `www/admin/js/cookies.js` | 修改 | 显示各平台 Cookie 诊断状态，不显示 Cookie 值 |
| `www/admin/css/admin.css` | 修改 | 管理后台列表、筛选、诊断面板样式整理 |
| `.env.example` | 修改 | 记录 `data/cookies.txt` 为运行期 Cookie 源，弱化根目录 Cookie 配置 |
| `docs/superpowers/frontend-session-checklist.md` | 修改 | 增加发布前管理后台与 Cookie 诊断检查项 |
| `docs/superpowers/worklogs/2026-04-19-v4-release-hardening.md` | 创建 | 记录本阶段实施、验证命令、已知边界 |
| `tests/test_admin_media_unittest.py` | 创建 | 覆盖全局媒体聚合、时间筛选、维护删除统计 |
| `tests/test_cookie_diagnostics_unittest.py` | 创建 | 覆盖 Cookie 关键字段诊断，不泄露值 |
| `tests/test_url_normalizer_unittest.py` | 创建 | 覆盖 B 站、YouTube、X/Twitter URL 规范化 |

---

## 任务 11：管理后台全局媒体聚合与筛选修复

**文件：**
- 修改：`server/video_library.py`
- 修改：`server/admin_api.py`
- 修改：`www/admin/js/render.js`
- 修改：`www/admin/css/admin.css`
- 创建：`tests/test_admin_media_unittest.py`
- 创建：`docs/superpowers/worklogs/2026-04-19-v4-release-hardening.md`

- [ ] **步骤 1：编写全局媒体聚合失败测试**

在 `tests/test_admin_media_unittest.py` 中创建内存数据库或临时 SQLite 场景：

```python
def test_admin_global_media_groups_user_items_by_asset():
    # 创建一个 MediaAsset，绑定两个 UserVideoItem。
    # 调用待实现的 list_admin_media_assets(session)。
    # 断言返回 1 个资产，owner_count == 2，owners 包含两个用户。
```

运行：

```powershell
venv\Scripts\python.exe -m unittest tests.test_admin_media_unittest
```

预期：失败，提示聚合查询函数不存在。

- [ ] **步骤 2：实现服务端聚合查询**

在 `server/video_library.py` 增加 `list_admin_media_assets(session, *, start_time=None, end_time=None, owner_id=None)`：

```python
def list_admin_media_assets(session, *, start_time=None, end_time=None, owner_id=None):
    query = session.query(MediaAsset)
    if start_time:
        query = query.filter(MediaAsset.created_at >= start_time)
    if end_time:
        query = query.filter(MediaAsset.created_at <= end_time)
    if owner_id:
        query = query.join(UserVideoItem).filter(UserVideoItem.owner_user_id == owner_id)
    assets = query.order_by(MediaAsset.created_at.desc()).all()
    return [build_admin_asset_summary(session, asset) for asset in assets]
```

摘要字段至少包括：`asset_id`、`title`、`file_hash`、`size_bytes`、`created_at`、`owner_count`、`owners`、`source_count`、`share_count`。

- [ ] **步骤 3：修复管理 API 时间筛选**

在 `server/admin_api.py` 中，把字符串时间先解析为 `datetime`，不要把 ISO 字符串传给本地时间转换函数。

```python
def _parse_optional_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
```

用该函数驱动全局媒体聚合 API。

- [ ] **步骤 4：前端改为按媒体资产展示**

在 `www/admin/js/render.js` 中，把全局视频库渲染从用户条目列表改为资产卡片或表格：

```javascript
// 每个物理媒体只展示一行。
// owners 显示为 “2 个用户” 并可展开用户名列表。
// 维护删除仍对 media_asset_id 调用。
```

- [ ] **步骤 5：验证与提交**

运行：

```powershell
venv\Scripts\python.exe -m unittest tests.test_admin_media_unittest
node --check www\admin\js\render.js
venv\Scripts\python.exe -m py_compile server\admin_api.py server\video_library.py
```

提交：

```powershell
git add server/video_library.py server/admin_api.py www/admin/js/render.js www/admin/css/admin.css tests/test_admin_media_unittest.py docs/superpowers/worklogs/2026-04-19-v4-release-hardening.md
git commit -m "fix(管理): 聚合展示全局媒体资产"
```

---

## 任务 12：Cookie 诊断面板

**文件：**
- 修改：`server/cookie_store.py`
- 修改：`server/admin_api.py`
- 修改：`www/admin/js/cookies.js`
- 修改：`www/admin/css/admin.css`
- 创建：`tests/test_cookie_diagnostics_unittest.py`
- 修改：`docs/superpowers/worklogs/2026-04-19-v4-release-hardening.md`

- [ ] **步骤 1：编写 Cookie 诊断失败测试**

在 `tests/test_cookie_diagnostics_unittest.py` 中覆盖：

```python
def test_cookie_diagnostics_reports_presence_without_values():
    content = (
        "# Netscape HTTP Cookie File\n"
        ".bilibili.com\tTRUE\t/\tTRUE\t0\tSESSDATA\tsecret\n"
        ".x.com\tTRUE\t/\tTRUE\t0\tauth_token\tsecret\n"
    )
    result = diagnose_cookie_content(content)
    assert result["bilibili"]["has_required"] is False
    assert "secret" not in str(result)
```

运行：

```powershell
venv\Scripts\python.exe -m unittest tests.test_cookie_diagnostics_unittest
```

预期：失败，提示诊断函数不存在。

- [ ] **步骤 2：实现平台关键字段诊断**

在 `server/cookie_store.py` 中增加：

```python
PLATFORM_COOKIE_REQUIREMENTS = {
    "bilibili": {"SESSDATA", "bili_jct", "DedeUserID"},
    "twitter": {"auth_token", "ct0"},
    "youtube": {"SAPISID", "__Secure-1PSID", "__Secure-3PSID"},
}
```

实现 `diagnose_cookie_content(content: str) -> dict`：

- 只读取 cookie 名称和域名。
- 返回每个平台 `present`、`missing`、`has_required`、`domains`。
- 绝不返回 cookie 值。

- [ ] **步骤 3：增加管理 API 字段**

在 `GET /cookies/status` 响应中增加：

```python
"diagnostics": diagnose_cookie_content(active_cookies.read_text(encoding="utf-8"))
```

- [ ] **步骤 4：前端显示诊断**

在 `www/admin/js/cookies.js` 的 Cookie 状态区域显示：

- B 站：完整/缺字段
- X/Twitter：完整/缺字段
- YouTube：完整/缺字段

缺字段只显示字段名，不显示值。

- [ ] **步骤 5：验证与提交**

运行：

```powershell
venv\Scripts\python.exe -m unittest tests.test_cookie_diagnostics_unittest tests.test_cookie_store_unittest
node --check www\admin\js\cookies.js
venv\Scripts\python.exe -m py_compile server\cookie_store.py server\admin_api.py
```

提交：

```powershell
git add server/cookie_store.py server/admin_api.py www/admin/js/cookies.js www/admin/css/admin.css tests/test_cookie_diagnostics_unittest.py docs/superpowers/worklogs/2026-04-19-v4-release-hardening.md
git commit -m "feat(cookie): 增加平台登录态诊断"
```

---

## 任务 13：URL 规范化与复用增强

**文件：**
- 创建：`server/url_normalizer.py`
- 修改：`server/api.py`
- 修改：`server/downloader.py`
- 修改：`server/video_library.py`
- 创建：`tests/test_url_normalizer_unittest.py`
- 修改：`docs/superpowers/worklogs/2026-04-19-v4-release-hardening.md`

- [ ] **步骤 1：编写 URL 规范化失败测试**

在 `tests/test_url_normalizer_unittest.py` 中覆盖：

```python
def test_youtube_watch_url_removes_progress_and_tracking():
    normalized = normalize_media_url("https://www.youtube.com/watch?v=abc123&t=30s&utm_source=x")
    assert normalized.canonical_url == "https://www.youtube.com/watch?v=abc123"
    assert normalized.platform == "youtube"
    assert normalized.media_key == "youtube:abc123"

def test_bilibili_url_removes_tracking_query():
    normalized = normalize_media_url("https://www.bilibili.com/video/BV14t4y1A7Tu/?spm_id_from=333.337.search-card.all.click")
    assert normalized.canonical_url == "https://www.bilibili.com/video/BV14t4y1A7Tu"
    assert normalized.media_key == "bilibili:BV14t4y1A7Tu"

def test_x_status_url_normalizes_domain():
    normalized = normalize_media_url("https://twitter.com/user/status/2042105224727269424?s=20")
    assert normalized.canonical_url == "https://x.com/i/status/2042105224727269424"
    assert normalized.media_key == "twitter:2042105224727269424"
```

运行：

```powershell
venv\Scripts\python.exe -m unittest tests.test_url_normalizer_unittest
```

预期：失败，模块不存在。

- [ ] **步骤 2：实现规范化模块**

创建 `server/url_normalizer.py`：

```python
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse, urlunparse

@dataclass(frozen=True)
class NormalizedMediaUrl:
    original_url: str
    canonical_url: str
    platform: str
    media_key: str
```

实现 `normalize_media_url(url: str) -> NormalizedMediaUrl`，只处理确定平台；未知平台返回去掉常见跟踪参数后的 URL，`media_key` 使用 canonical URL。

- [ ] **步骤 3：下载提交前使用 canonical URL 复用**

在 `server/api.py` 创建任务前：

```python
normalized = normalize_media_url(request.url)
source_url = normalized.canonical_url
```

复用查找优先使用 `media_key`，其次使用 canonical URL，再保留原始 URL 入 `meta.original_url`。

- [ ] **步骤 4：登记来源时补强 media_key**

在 `server/video_library.py` 的 `MediaSource` 登记逻辑中保存：

- `original_url`
- `canonical_url`
- `media_key`
- `platform`

如果当前表结构没有字段，先把这些值放进 `meta`，不要立即做破坏性迁移。

- [ ] **步骤 5：验证与提交**

运行：

```powershell
venv\Scripts\python.exe -m unittest tests.test_url_normalizer_unittest tests.test_download_cancellation_unittest tests.test_downloader_transfer_boundaries_unittest
venv\Scripts\python.exe -m py_compile server/url_normalizer.py server/api.py server/downloader.py server/video_library.py
```

提交：

```powershell
git add server/url_normalizer.py server/api.py server/downloader.py server/video_library.py tests/test_url_normalizer_unittest.py docs/superpowers/worklogs/2026-04-19-v4-release-hardening.md
git commit -m "feat(下载): 增强平台 URL 规范化复用"
```

---

## 任务 14：发布前配置与数据巡检

**文件：**
- 修改：`.env.example`
- 创建：`server/health_checks.py`
- 修改：`server/admin_api.py`
- 创建：`tests/test_health_checks_unittest.py`
- 修改：`docs/superpowers/frontend-session-checklist.md`
- 修改：`docs/superpowers/worklogs/2026-04-19-v4-release-hardening.md`

- [ ] **步骤 1：编写巡检失败测试**

创建 `tests/test_health_checks_unittest.py`：

```python
def test_health_check_reports_runtime_cookie_source():
    result = collect_runtime_health()
    assert "cookie_source" in result
    assert "download_dir_writable" in result
    assert "database_writable" in result
```

运行：

```powershell
venv\Scripts\python.exe -m unittest tests.test_health_checks_unittest
```

预期：失败，模块不存在。

- [ ] **步骤 2：实现健康巡检模块**

创建 `server/health_checks.py`，返回：

- 当前分支或版本信息
- `data/cookies.txt` 是否存在
- Cookie 诊断摘要
- 下载目录是否可写
- 数据库是否可打开
- `ffmpeg` 是否可用
- yt-dlp 版本

- [ ] **步骤 3：管理 API 暴露管理员巡检接口**

在 `server/admin_api.py` 增加：

```python
@router.get("/runtime/health")
async def get_runtime_health(admin: User = Depends(require_admin)) -> dict:
    return collect_runtime_health()
```

- [ ] **步骤 4：更新配置文档**

在 `.env.example` 中明确：

```env
# 仅作为首次导入旧 Cookie 使用；运行期 Cookie 由 data/cookies.txt 管理。
GOTUBE_COOKIES_FILE=./cookies.txt
```

在 `docs/superpowers/frontend-session-checklist.md` 增加发布前检查项：

- 管理员 Cookie 诊断均为可接受状态。
- `/admin/api/runtime/health` 无阻断项。
- 下载目录与数据库可写。

- [ ] **步骤 5：验证与提交**

运行：

```powershell
venv\Scripts\python.exe -m unittest tests.test_health_checks_unittest tests.test_cookie_store_unittest
venv\Scripts\python.exe -m py_compile server/health_checks.py server/admin_api.py
```

提交：

```powershell
git add .env.example server/health_checks.py server/admin_api.py tests/test_health_checks_unittest.py docs/superpowers/frontend-session-checklist.md docs/superpowers/worklogs/2026-04-19-v4-release-hardening.md
git commit -m "feat(运维): 增加 V4 发布前运行巡检"
```

---

## 任务 15：V4.0.0 合并前最终验收包

**文件：**
- 创建：`docs/superpowers/v4-release-checklist.md`
- 修改：`docs/superpowers/task-10-acceptance-summary.md`
- 修改：`docs/superpowers/worklogs/2026-04-19-v4-release-hardening.md`

- [ ] **步骤 1：创建最终验收清单**

创建 `docs/superpowers/v4-release-checklist.md`，包括：

- 自动化测试命令
- 手工验收 9 组结论
- 管理后台补测项
- Cookie 诊断补测项
- URL 规范化补测项
- 回滚策略

- [ ] **步骤 2：执行最终自动化验证**

运行：

```powershell
venv\Scripts\python.exe -m unittest tests.test_download_cancellation_unittest tests.test_cookie_store_unittest tests.test_downloader_error_messages_unittest tests.test_frontend_session_contract_unittest tests.test_downloader_transfer_boundaries_unittest tests.test_admin_media_unittest tests.test_cookie_diagnostics_unittest tests.test_url_normalizer_unittest tests.test_health_checks_unittest
node --check www\download.js
node --check www\admin\js\cookies.js
node --check www\admin\js\render.js
venv\Scripts\python.exe -m py_compile server\downloader.py server\queue_manager.py server\admin_api.py server\cookie_store.py server\url_normalizer.py server\health_checks.py server\main.py
git diff --check
```

- [ ] **步骤 3：记录最终结果**

在 `docs/superpowers/v4-release-checklist.md` 填入命令结果与手工补测结论。

- [ ] **步骤 4：提交文档**

```powershell
git add docs/superpowers/v4-release-checklist.md docs/superpowers/task-10-acceptance-summary.md docs/superpowers/worklogs/2026-04-19-v4-release-hardening.md
git commit -m "docs(发布): 增加 V4.0.0 最终验收清单"
```

---

## 执行顺序

1. 任务 11：管理后台全局媒体聚合与筛选修复。
2. 任务 12：Cookie 诊断面板。
3. 任务 13：URL 规范化与复用增强。
4. 任务 14：发布前配置与数据巡检。
5. 任务 15：V4.0.0 合并前最终验收包。

每个任务完成后都应：

```powershell
git status --short
git log --oneline -3
```

并将分支推送到：

```powershell
git push origin codex/v4-multi-user-library
```

## 暂不纳入 V4.0.0 的事项

- 普通用户个人 Cookie 上传，优先级保持最低。
- 管理后台完整视觉重做，只做必要结构修复与可维护性提升。
- 深度平台解析能力替代 yt-dlp，不在当前版本范围内。
