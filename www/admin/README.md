# GoTube 管理页面

视频库管理模块，提供登录认证、视频浏览、筛选、标签管理、导出和批量删除等功能。

## 目录结构

```
www/
├── common.js               # 公共工具函数（$、el、apiFetch、formatBytes 等）
└── admin/
    ├── admin.html          # 管理页面入口 HTML
    ├── README.md           # 本文档
    ├── js/
    │   ├── state.js        # 全局状态管理（state 对象 + goToPage）
    │   ├── toast.js        # Toast 提示系统（showToast）
    │   ├── auth.js         # 认证模块（登录、登出、Token 验证）
    │   ├── render.js       # 页面渲染（导航栏、筛选栏、视频网格、分页、批量操作栏）
    │   ├── data.js         # 数据操作（加载视频、删除、批量删除、标签更新）
    │   ├── export.js       # 导出功能（ZIP、JSON、m3u8）
    │   ├── events.js       # 事件处理（筛选、标签、选择、下拉菜单）
    │   ├── modals.js       # 模态框（播放器、分享、标签管理、删除确认）
    │   └── admin.js        # 主入口（初始化 + 全局事件监听）
    └── css/
        └── admin.css       # 样式文件（CSS 变量、布局、组件样式）
```

## 加载顺序

`admin.html` 按以下依赖顺序加载脚本：

1. `common.js` → 基础工具函数（`$`, `$$`, `el`, `apiFetch`, `formatBytes`, `injectStyles` 等）
2. `js/state.js` → 全局状态对象（必须第二个加载）
3. `js/toast.js` → Toast 提示
4. `js/auth.js` → 认证（依赖 state.js）
5. `js/render.js` → 页面渲染（依赖 state.js, data.js, export.js, events.js, modals.js）
6. `js/data.js` → 数据操作（依赖 state.js, toast.js, modals.js）
7. `js/export.js` → 导出功能（依赖 state.js）
8. `js/events.js` → 事件处理（依赖 state.js, render.js）
9. `js/modals.js` → 模态框（依赖 state.js, data.js, events.js）
10. `js/admin.js` → 主入口（最后加载，负责初始化和全局事件）

> ⚠️ **重要**: 新增模块时必须在 `admin.html` 中按正确依赖顺序添加 `<script>` 标签。

## 模块说明

### common.js
公共工具库（位于 `www/common.js`），提供所有页面共享的基础函数：
- `$` / `$$` - DOM 查询快捷方式
- `el` - DOM 元素创建
- `apiFetch` - 带认证的 API 请求封装
- `formatBytes` / `formatSpeed` / `formatETA` - 格式化工具
- `extractSource` - 从 URL 提取来源平台
- `getApiBase` - 获取 API 基础路径
- `injectStyles` - 动态加载 CSS（优先加载外部 `admin.css`，失败时回退到内联样式）

### js/state.js
全局状态数据中心：
- `state` 对象：视频列表、筛选条件、分页、选中项等
- `goToPage()` - 分页跳转

### js/toast.js
用户提示系统：
- `showToast(message, type, duration)` - 显示 Toast（success/error/warning/info）

### js/auth.js
认证相关功能：
- `checkAuth()` - 检查 Token 有效性
- `showLoginForm()` / `hideLoginForm()` - 登录表单显示/隐藏
- `handleLogin()` - 处理登录
- `handleLogout()` - 退出登录

### js/render.js
页面 UI 渲染：
- `renderPage()` - 渲染整个管理页面（入口）
- `renderNavbar()` - 导航栏
- `renderStatsPanel()` / `toggleStatsPanel()` - 统计面板
- `renderFilters()` / `renderSelectedTags()` - 筛选栏
- `renderVideoGrid()` / `renderVideoCard()` - 视频网格
- `renderPagination()` - 分页控件
- `renderBatchBar()` / `updateBatchBar()` - 批量操作栏

### js/data.js
数据操作：
- `loadVideos()` / `loadStats()` - 加载数据
- `handleDeleteVideo()` / `showDeleteConfirmModal()` / `executeDeleteVideo()` - 单个删除
- `handleBatchDelete()` - 批量删除
- `updateTags()` / `removeVideoTag()` - 标签管理

### js/export.js
导出功能：
- `handleExportZip()` - 导出 ZIP
- `handleExportJson()` - 导出 JSON 元数据
- `handleExportM3u8()` - 导出播放列表

### js/events.js
用户交互事件：
- `handleKeywordChange()` - 关键词搜索（带防抖）
- `handleSourceChange()` / `handleTimeChange()` - 筛选变化
- `handleTagInputKeydown()` / `removeFilterTag()` - 标签输入
- `toggleVideoSelection()` / `clearSelection()` - 视频选择
- `toggleDropdown()` / `hideAllDropdowns()` - 下拉菜单

### js/modals.js
模态框管理：
- `showPlayerModal()` - 视频播放器
- `showShareModal()` - 分享链接
- `showTagManagerModal()` / `renderModalTags()` - 标签管理器
- `closeModal()` - 关闭模态框

### js/admin.js
主入口文件：
- `DOMContentLoaded` 事件监听
- 调用 `injectStyles()` 和 `checkAuth()`
- 全局事件监听（点击关闭下拉菜单、ESC 关闭模态框）

### css/admin.css
样式文件：
- CSS 变量定义（颜色、背景等）
- 所有组件样式（导航栏、筛选栏、视频网格、模态框、Toast 等）
- 响应式设计
- 动画（Toast 滑入滑出、登录错误抖动）

## 开发指南

### 添加新功能

1. **确定模块归属**：新功能属于哪个模块？
   - UI 变更 → `render.js`
   - 数据操作 → `data.js`
   - 用户交互 → `events.js`
   - 弹窗/对话框 → `modals.js`
   - 新的导出格式 → `export.js`
   - 新的提示类型 → `toast.js`
   - 新的状态字段 → `state.js`

2. **在对应模块中添加函数**，保持现有代码风格

3. **如需新模块**：
   - 在 `js/` 下创建新文件（如 `js/settings.js`）
   - 在 `admin.html` 中按依赖顺序添加 `<script>` 标签
   - 更新本 README 的模块说明

### 代码规范

- 使用 JSDoc 注释所有函数
- 函数命名：动词开头（`show`, `handle`, `render`, `load` 等）
- 全局状态统一通过 `state` 对象访问
- DOM 操作使用 `$` 和 `el` 工具函数
- API 调用使用 `apiFetch`（自动处理 Token）
- 用户反馈使用 `showToast`（避免 `alert`）

### 调试技巧

- 浏览器控制台可查看 `state` 对象（全局可用）
- 网络面板查看 API 请求（自动携带 Bearer Token）
- 修改 CSS 后刷新即可生效（无缓存问题，因为 HTML 中带有版本号）

## 后端 API 依赖

管理页面前端依赖以下后端 API（定义在 `server/admin_api.py`）：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/login` | POST | 登录获取 Token |
| `/api/auth/check` | GET | 验证 Token |
| `/api/videos` | GET | 获取视频列表（支持分页和筛选） |
| `/api/videos/{filename}` | DELETE | 删除单个视频 |
| `/api/videos/batch-delete` | POST | 批量删除 |
| `/api/videos/{filename}/tags` | PUT | 更新标签 |
| `/api/export/zip` | POST | 导出 ZIP |
| `/api/export/json` | POST | 导出 JSON |
| `/api/export/m3u8` | POST | 导出 m3u8 |
| `/api/stats` | GET | 获取统计信息 |

## 历史

- **2026-04-12**: 初始版本创建（单文件 admin.js，1509 行）
- **2026-04-12**: 模块化重构（拆分为 9 个模块 + CSS，平均 150 行/文件）
