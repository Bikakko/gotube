# 4.7.0 前端结构整理计划

## 目标

在不改变现有用户功能和页面路由的前提下，先完成一轮前端结构收口：

1. 将页面行为从 HTML 内联事件迁移到 JavaScript 初始化逻辑。
2. 统一页面初始化入口，减少全局散落的事件绑定方式。
3. 在保持 `window.GoTube` 共享边界的前提下，收清下载页与首页的页面私有逻辑。
4. 为后续 `www/` 目录按页面拆分做准备，但本阶段不做大规模路径搬迁。

## 边界

- 本阶段不修改页面 URL、服务端路由和静态资源目录结构。
- 本阶段不改动下载任务流、游客会话逻辑、管理后台鉴权流程。
- 本阶段允许保留必要的 `window.DownloadPage` / `window.GoTube.home` 导出，但 HTML 不再依赖内联调用。

## 任务拆分

### 任务 1：下载页去内联事件

范围：

- `www/download.html`
- `www/download.js`
- `tests/test_frontend_build_setup_unittest.py`

目标：

- 移除下载页中的 `onclick`、`onsubmit` 等内联行为。
- 由 `download.js` 统一完成：
  - 表单提交拦截
  - 模态框遮罩关闭
  - 按钮点击绑定
  - Escape 关闭逻辑
- 保持现有 `window.DownloadPage` 能力不变，避免误伤其它脚本或调试路径。

验收：

- `download.html` 不再包含下载页内联行为属性。
- `download.js` 具备单一初始化入口。
- 现有下载、登录、注册、模态框关闭逻辑不回归。

### 任务 2：首页初始化收口

范围：

- `www/index.js`
- `tests/test_frontend_build_setup_unittest.py`

目标：

- 明确首页初始化入口。
- 将场景初始化、模态交互、隐藏入口联动分层组织。
- 避免首页后续继续把页面行为散落在全局顶层。

### 任务 3：共享与页面私有逻辑分层

范围：

- `www/common.js`
- `www/download.js`
- `www/index.js`
- 对应测试与文档

目标：

- `common.js` 仅保留真正共享能力。
- 页面私有 UI 逻辑不再向共享文件泄漏。
- 统一 `bootstrap()` / `init()` 风格。

### 任务 4：目录结构重组预案

范围：

- 仅文档，不实施搬迁

目标：

- 设计下一阶段 `www/` 目录重组方案：
  - `shared/`
  - `download/`
  - `home/`
  - `admin/`
- 明确服务端页面读取与构建脚本的迁移方式。

## 验证策略

每个任务至少执行：

- `node --check` 对相关脚本做语法检查
- `node build.js`
- 相关 `python -m unittest ...`

## 风险控制

- 含中文页面文件仅做局部修改，避免编码污染。
- 先去掉 HTML 内联行为，再考虑更大的 JS 拆分。
- 只在现有路径稳定后，再进入目录迁移阶段。
