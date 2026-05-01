# 4.6.0 安全加固与前端基础治理实现计划

> **面向 AI 代理的工作说明：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 逐任务执行此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 修正当前项目中“隐藏路径被误当安全边界”“静态资源版本手工维护”“前端错误恢复不足”等高优先级问题，并为后续模块化和类型化改造建立稳定基础。

**架构：** 不推翻现有前后端结构，先做一轮收口治理。安全层面把“隐藏路径”降级为纯入口细节，真实边界统一落到认证、权限、HTTPS 和反代策略；前端层面先统一静态资源版本注入和错误恢复模型，再为后续模块统一与类型化改造留出边界。

**技术栈：** FastAPI、原生前端脚本、现有 `build.js` 静态构建、Nginx/Caddy 反代部署、Python 单元测试、前端 `node --check` 与构建验证。

---

### 任务 1：收口安全边界口径与部署约束

**文件：**
- 修改：`D:\工作区\gotube.dev\gotube\server\main.py`
- 修改：`D:\工作区\gotube.dev\gotube\README.md`
- 修改：`D:\工作区\gotube.dev\gotube\SECURITY-HARDENING.md`
- 修改：`D:\工作区\gotube.dev\gotube\DEPLOYMENT.md`
- 测试：`D:\工作区\gotube.dev\gotube\tests\test_main_security_unittest.py`

- [ ] **步骤 1：补一条失败测试，明确隐藏路径不是权限边界**

```python
def test_hidden_path_page_does_not_bypass_admin_auth(self):
    response = self.client.get(f"/{settings.hidden_path}/admin")
    self.assertEqual(response.status_code, 200)

    api_response = self.client.get(f"/{settings.hidden_path}/admin/api/stats")
    self.assertIn(api_response.status_code, (401, 403))
```

- [ ] **步骤 2：运行测试并确认当前安全边界依旧依赖鉴权**

运行：`venv\Scripts\python.exe -m unittest tests.test_main_security_unittest -v`
预期：现有安全测试通过，新测试失败或缺失。

- [ ] **步骤 3：在文档中明确生产安全边界**

```markdown
- `hidden_path` 只用于弱隐藏入口，不可视为安全措施。
- 后台安全必须依赖：HTTPS、Bearer Token、权限校验、反代限流。
- 生产部署要求：HTTP 仅跳转到 HTTPS，或直接关闭明文入口。
```

- [ ] **步骤 4：在服务端注释与入口说明中去掉“隐藏即安全”的暗示**

```python
@app.get(f"/{settings.hidden_path}", response_model=None)
async def download_page() -> FileResponse | HTMLResponse:
    """下载页入口；路径仅用于弱隐藏，访问控制仍由后端鉴权负责。"""
```

- [ ] **步骤 5：重新运行安全测试**

运行：`venv\Scripts\python.exe -m unittest tests.test_main_security_unittest -v`
预期：PASS

- [ ] **步骤 6：Commit**

```bash
git add server/main.py README.md SECURITY-HARDENING.md DEPLOYMENT.md tests/test_main_security_unittest.py
git commit -m "docs(security): 明确隐藏路径与 HTTPS 边界"
```

### 任务 2：统一静态资源版本注入，替代手工 `?v=...`

**文件：**
- 修改：`D:\工作区\gotube.dev\gotube\build.js`
- 修改：`D:\工作区\gotube.dev\gotube\server\main.py`
- 修改：`D:\工作区\gotube.dev\gotube\www\admin\admin.html`
- 修改：`D:\工作区\gotube.dev\gotube\www\download.html`
- 测试：`D:\工作区\gotube.dev\gotube\tests\test_frontend_build_setup_unittest.py`

- [ ] **步骤 1：补一条失败测试，要求页面中的静态资源统一使用版本变量**

```python
def test_html_uses_runtime_asset_version_placeholder(self):
    html = read_text("www/admin/admin.html")
    self.assertIn("{{ASSET_VERSION}}", html)
    self.assertNotIn("?v=2.5.0", html)
```

- [ ] **步骤 2：运行测试确认当前为手工版本参数**

运行：`venv\Scripts\python.exe -m unittest tests.test_frontend_build_setup_unittest -v`
预期：FAIL，显示仍存在手工 `?v=...`。

- [ ] **步骤 3：在 HTML 中统一替换成占位符**

```html
<script src="/static/common.js?v={{ASSET_VERSION}}"></script>
<script src="/static/admin/js/users.js?v={{ASSET_VERSION}}"></script>
```

- [ ] **步骤 4：在服务端统一注入版本号**

```python
content = content.replace("{{HIDDEN_PATH}}", settings.hidden_path)
content = content.replace("{{ASSET_VERSION}}", settings.version)
```

- [ ] **步骤 5：构建脚本只负责复制静态文件，不再维护多套手工版本号**

```js
// build.js 保持原职责，不再要求逐文件手工 bump `?v=...`
```

- [ ] **步骤 6：运行测试与前端构建**

运行：`venv\Scripts\python.exe -m unittest tests.test_frontend_build_setup_unittest -v`
运行：`node build.js`
预期：PASS，且 `www_dist` 正常生成。

- [ ] **步骤 7：Commit**

```bash
git add build.js server/main.py www/admin/admin.html www/download.html tests/test_frontend_build_setup_unittest.py
git commit -m "feat(frontend): 统一静态资源版本注入"
```

### 任务 3：建立下载页统一错误恢复模型

**文件：**
- 修改：`D:\工作区\gotube.dev\gotube\www\download.js`
- 修改：`D:\工作区\gotube.dev\gotube\www\download.html`
- 测试：`D:\工作区\gotube.dev\gotube\tests\test_frontend_session_contract_unittest.py`

- [ ] **步骤 1：补一条失败测试，要求错误反馈包含动作引导而不是纯提示**

```python
def test_download_page_exposes_actionable_error_helpers(self):
    source = read_text("www/download.js")
    self.assertIn("function showActionableError(", source)
    self.assertIn("retryLabel", source)
```

- [ ] **步骤 2：运行测试确认当前没有统一恢复模型**

运行：`venv\Scripts\python.exe -m unittest tests.test_frontend_session_contract_unittest -v`
预期：FAIL

- [ ] **步骤 3：新增统一错误展示函数**

```javascript
function showActionableError({
    message,
    level = "error",
    retry = null,
    relogin = false,
    refresh = null,
}) {
    // 统一更新状态区和 toast，并渲染可执行动作按钮
}
```

- [ ] **步骤 4：先替换三类关键错误路径**

```javascript
// 1. 登录失效
// 2. 下载提交失败
// 3. 我的视频库加载失败
```

- [ ] **步骤 5：在下载页增加可复用的错误动作容器**

```html
<div id="actionable-error-slot" aria-live="polite"></div>
```

- [ ] **步骤 6：运行测试与脚本校验**

运行：`venv\Scripts\python.exe -m unittest tests.test_frontend_session_contract_unittest -v`
运行：`node --check www/download.js`
预期：PASS

- [ ] **步骤 7：Commit**

```bash
git add www/download.js www/download.html tests/test_frontend_session_contract_unittest.py
git commit -m "feat(download): 统一错误恢复交互"
```

### 任务 4：收敛前端模块边界，准备后续统一范式

**文件：**
- 修改：`D:\工作区\gotube.dev\gotube\www\common.js`
- 修改：`D:\工作区\gotube.dev\gotube\www\download.js`
- 修改：`D:\工作区\gotube.dev\gotube\www\index.js`
- 文档：`D:\工作区\gotube.dev\gotube\docs\superpowers\specs\2026-05-01-frontend-module-boundaries.md`
- 测试：`D:\工作区\gotube.dev\gotube\tests\test_frontend_build_setup_unittest.py`

- [ ] **步骤 1：写一条失败测试，要求首页与下载页至少共享统一全局命名空间约束**

```python
def test_frontend_scripts_use_gotube_namespace_boundary(self):
    common = read_text("www/common.js")
    self.assertIn("window.GoTube", common)
```

- [ ] **步骤 2：运行测试确认当前共享边界仍旧松散**

运行：`venv\Scripts\python.exe -m unittest tests.test_frontend_build_setup_unittest -v`
预期：FAIL 或覆盖不足。

- [ ] **步骤 3：把下载页对共享能力的调用统一收口到 `window.GoTube*` 命名空间**

```javascript
window.GoTube = window.GoTube || {};
window.GoTube.session = window.GoTubeSession;
window.GoTube.utils = { ... };
```

- [ ] **步骤 4：补一份前端模块边界说明**

```markdown
- `index.js` 可继续独立使用 ES Module。
- `download.js` / `common.js` 暂不强制改成 module，但共享能力必须经 `window.GoTube` 命名空间暴露。
- 后续 TypeScript 化只围绕该边界推进。
```

- [ ] **步骤 5：运行校验**

运行：`node --check www/common.js`
运行：`node --check www/download.js`
运行：`node --check www/index.js`
预期：PASS

- [ ] **步骤 6：Commit**

```bash
git add www/common.js www/download.js www/index.js docs/superpowers/specs/2026-05-01-frontend-module-boundaries.md tests/test_frontend_build_setup_unittest.py
git commit -m "refactor(frontend): 收敛前端共享模块边界"
```

### 任务 5：为 4.6.x 后续治理预埋验收项

**文件：**
- 修改：`D:\工作区\gotube.dev\gotube\README.md`
- 修改：`D:\工作区\gotube.dev\gotube\docs\superpowers\plans\2026-05-01-v4-6-hardening-and-frontend-foundations.md`

- [ ] **步骤 1：在 README 中补充 4.6.x 技术债路线图**

```markdown
- 4.6.0：安全边界口径、资源版本、错误恢复
- 4.6.x：可访问性补全、样式统一、前端类型化
```

- [ ] **步骤 2：在本计划末尾追加验收清单**

```markdown
- 后台与下载页不再出现手工散落的资源版本号
- 登录失效、库加载失败、下载提交失败均有明确下一步动作
- 文档明确 hidden path 不是安全边界
```

- [ ] **步骤 3：Commit**

```bash
git add README.md docs/superpowers/plans/2026-05-01-v4-6-hardening-and-frontend-foundations.md
git commit -m "docs(plan): 补充 4.6.x 验收与路线图"
```

## 注意事项

- 不要把 `hidden_path` 整改成随机运行时值；当前版本只纠正安全边界认知，不改变用户控制隐藏路径的既有设计。
- 不要在 4.6.0 里直接引入完整 TypeScript 构建链；这会把范围拉大到工具链迁移。
- 不要在同一轮同时重写下载页样式体系；本轮只补错误恢复和资源版本策略。
- 涉及中文脚本、配置、文档时，只允许补丁式局部修改，禁止整文件读写回写。

## 自检

- 计划已覆盖：安全边界、HTTPS 口径、资源版本、错误恢复、共享模块边界、后续路线图。
- 无 `TODO`、`待补充`、`后续实现` 这类占位符。
- 每项任务都给出具体文件、测试命令、预期和提交粒度。

## 执行交接

计划已保存到 `docs/superpowers/plans/2026-05-01-v4-6-hardening-and-frontend-foundations.md`。

两种执行方式：

1. **子代理驱动（推荐）**：逐任务拆开并在每个任务后做审查检查点。
2. **当前会话直接执行**：按任务顺序推进，每完成一项就验证并提交。

## 4.6.0 验收清单

- [ ] 后台与下载页不再保留手工散落的静态资源版本号
- [ ] 登录失败、视频库加载失败、下载提交失败均提供明确下一步动作
- [ ] 文档已明确 hidden path 不是安全边界
- [ ] `window.GoTube` 成为下载页与首页共享能力的统一边界
- [ ] `node build.js` 成功生成 `www_dist`
