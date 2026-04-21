# GoTube V5.0.0 门户首页与 NinLucky 接入实现计划

> **面向 AI 代理的工作者：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 将 GoTube 升级为统一入口站，首页提供 `GoTube` 与“您吉祥”两个入口，并通过 `/ninlucky/` 接入独立部署的 GameHub。

**架构：** GoTube 继续作为主站与统一身份提供方；GameHub 保持独立仓库、独立构建、独立后端；主页负责入口组织，Nginx 负责同域路径接入。

**技术栈：** FastAPI、现有 `www/` 静态页体系、GoTube 认证接口、Nginx 反向代理、GameHub 独立前后端。

---

## 文件结构

### 本计划预计修改或新增的 GoTube 文件

- 修改：`www/index.html`
  - 将根路径页面重构为门户首页。
- 新增：`www/index.js`
  - 渲染门户入口、用户状态和站点级交互。
- 新增：`www/index.css`
  - 门户首页样式。
- 修改：`server/main.py`
  - 保持 `/` 指向门户首页，必要时补模板变量。
- 新增：`tests/test_portal_home_unittest.py`
  - 验证门户首页结构、入口配置和关键路径语义。
- 修改：`操作说明.md`
  - 增补 V5 门户入口说明。
- 新增：`docs/ops/ninlucky-reverse-proxy.md`
  - 记录 `/ninlucky/` 同域反代接入方式。

### 需要参考但不直接修改的外部项目

- `D:/工作区/gamehub/docs/technical.md`
- `D:/工作区/gamehub/docs/api-spec.md`
- `D:/工作区/gamehub/docs/game-dev-guide.md`

---

### 任务 1：重建根路径为门户首页

**文件：**
- 修改：`www/index.html`
- 新增：`www/index.js`
- 新增：`www/index.css`
- 测试：`tests/test_portal_home_unittest.py`

- [ ] **步骤 1：编写首页门户结构测试**

```python
def test_portal_home_contains_two_app_entries(self):
    html = (ROOT / "www/index.html").read_text(encoding="utf-8")
    self.assertIn('data-app-key="gotube"', html)
    self.assertIn('data-app-key="ninlucky"', html)
```

- [ ] **步骤 2：运行测试确认失败**

运行：
```bash
.\venv\Scripts\python.exe -m unittest tests.test_portal_home_unittest
```

预期：
- FAIL
- 报错提示首页尚未包含门户入口结构

- [ ] **步骤 3：实现门户首页最小骨架**

```html
<main id="portal-app">
  <section id="portal-entry-list">
    <article data-app-key="gotube"></article>
    <article data-app-key="ninlucky"></article>
  </section>
</main>
```

- [ ] **步骤 4：补首页入口配置驱动渲染**

```js
const PORTAL_APPS = [
  { key: 'gotube', displayName: 'GoTube', path: '/{{HIDDEN_PATH}}' },
  { key: 'ninlucky', displayName: '您吉祥', path: '/ninlucky/' },
];
```

- [ ] **步骤 5：运行测试验证通过**

运行：
```bash
.\venv\Scripts\python.exe -m unittest tests.test_portal_home_unittest
```

预期：
- PASS

- [ ] **步骤 6：Commit**

```bash
git add www/index.html www/index.js www/index.css tests/test_portal_home_unittest.py
git commit -m "feat(portal): 新增 V5 门户首页骨架"
```

### 任务 2：固化应用入口配置模型

**文件：**
- 修改：`www/index.js`
- 测试：`tests/test_portal_home_unittest.py`

- [ ] **步骤 1：编写入口配置结构测试**

```python
def test_portal_config_keeps_display_name_and_path_separate(self):
    source = (ROOT / "www/index.js").read_text(encoding="utf-8")
    self.assertIn("displayName", source)
    self.assertIn("path", source)
    self.assertIn("/ninlucky/", source)
    self.assertIn("您吉祥", source)
```

- [ ] **步骤 2：运行测试确认失败**

运行：
```bash
.\venv\Scripts\python.exe -m unittest tests.test_portal_home_unittest
```

预期：
- FAIL

- [ ] **步骤 3：实现统一入口配置模型**

```js
const PORTAL_APPS = [
  {
    key: 'gotube',
    displayName: 'GoTube',
    path: `/${GOTUBE_HIDDEN_PATH}`,
    description: '下载与视频库',
    status: 'active',
  },
  {
    key: 'ninlucky',
    displayName: '您吉祥',
    path: '/ninlucky/',
    description: '页面游戏平台',
    status: 'active',
  },
];
```

- [ ] **步骤 4：运行测试验证通过**

运行：
```bash
.\venv\Scripts\python.exe -m unittest tests.test_portal_home_unittest
```

预期：
- PASS

- [ ] **步骤 5：Commit**

```bash
git add www/index.js tests/test_portal_home_unittest.py
git commit -m "feat(portal): 抽象首页应用入口配置"
```

### 任务 3：明确首页与原业务入口边界

**文件：**
- 修改：`server/main.py`
- 测试：`tests/test_portal_home_unittest.py`

- [ ] **步骤 1：编写路由边界测试**

```python
def test_main_routes_keep_hidden_download_admin_and_watch(self):
    source = (ROOT / "server/main.py").read_text(encoding="utf-8")
    self.assertIn('async def root_page', source)
    self.assertIn('async def download_page', source)
    self.assertIn('async def admin_page', source)
    self.assertIn('async def watch_unified', source)
```

- [ ] **步骤 2：运行测试确认当前基线**

运行：
```bash
.\venv\Scripts\python.exe -m unittest tests.test_portal_home_unittest
```

预期：
- 现有测试通过或新增断言失败

- [ ] **步骤 3：补首页模板变量与入口文案注入**

```python
content = content.replace("{{HIDDEN_PATH}}", settings.hidden_path)
```

- [ ] **步骤 4：运行测试验证通过**

运行：
```bash
.\venv\Scripts\python.exe -m unittest tests.test_portal_home_unittest
```

预期：
- PASS

- [ ] **步骤 5：Commit**

```bash
git add server/main.py tests/test_portal_home_unittest.py
git commit -m "refactor(portal): 固化首页与原业务路由边界"
```

### 任务 4：补 NinLucky 接入与反代文档

**文件：**
- 新增：`docs/ops/ninlucky-reverse-proxy.md`
- 修改：`操作说明.md`

- [ ] **步骤 1：编写同域反代说明**

```md
- `/` 由 GoTube 提供
- `/ninlucky/` 反代到独立 GameHub 服务
- GameHub 保持独立部署
```

- [ ] **步骤 2：编写最小 Nginx 路由示例**

```nginx
location /ninlucky/ {
    proxy_pass http://127.0.0.1:5174/;
}
```

- [ ] **步骤 3：在操作说明中补入口说明**

```md
- 根路径 `/`：统一门户
- `/{hidden_path}`：GoTube 下载页
- `/ninlucky/`：您吉祥
```

- [ ] **步骤 4：人工检查文档链接与路径**

运行：
```bash
git diff -- docs/ops/ninlucky-reverse-proxy.md 操作说明.md
```

预期：
- 链接有效
- 路径语义一致

- [ ] **步骤 5：Commit**

```bash
git add docs/ops/ninlucky-reverse-proxy.md 操作说明.md
git commit -m "docs(portal): 补充 NinLucky 接入部署说明"
```

### 任务 5：补门户验收清单并收口版本文案

**文件：**
- 新增：`docs/superpowers/v5-portal-acceptance-checklist.md`
- 修改：`VERSION`
- 修改：必要的版本说明文档

- [ ] **步骤 1：编写门户验收清单**

```md
- 首页显示 GoTube 与您吉祥入口
- GoTube 入口跳转正确
- `/ninlucky/` 入口跳转正确
- 游客与已登录状态展示正常
```

- [ ] **步骤 2：统一版本文案到 V5.0.0**

```text
VERSION -> 5.0.0
```

- [ ] **步骤 3：运行最小回归验证**

运行：
```bash
.\venv\Scripts\python.exe -m unittest tests.test_portal_home_unittest tests.test_start_script_unittest
```

预期：
- PASS

- [ ] **步骤 4：Commit**

```bash
git add docs/superpowers/v5-portal-acceptance-checklist.md VERSION
git commit -m "chore(release): 收口 V5 门户验收清单"
```

## 自检

- 本计划只覆盖 V5.0.0 门户首页与 NinLucky 接入，不包含 GameHub 仓库内部实现任务。
- 本计划已明确文件职责，没有使用“待定”“后续补充”之类占位语。
- 首页、入口配置、路由边界、接入文档、验收清单五块内容均有对应任务。
- 与外部 GameHub 的边界清晰：只接入、不并仓、不共库。

## 执行交接

计划已完成并保存到 `docs/superpowers/plans/2026-04-21-gotube-v5-portal-ninlucky.md`。两种执行方式：

**1. 子代理驱动（推荐）**  
每个任务调度一个新子代理，任务间进行审查，适合门户页、文档和路由边界并行推进。

**2. 内联执行**  
在当前会话中直接分任务实现，适合保持 GoTube 主仓库单线推进。

建议先由你审阅设计文档，再决定是否进入实现。
