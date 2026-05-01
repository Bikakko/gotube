# 2026-05-01 任务 1：下载页去内联事件

## 目标

将下载页的 HTML 内联行为迁移到 `www/download.js`，让页面结构与页面行为解耦。

## 本次改动

- 移除 `www/download.html` 中的：
  - `onclick`
  - `onsubmit`
  - `onkeypress`
- 为模态框关闭按钮补充稳定的 DOM 标识：
  - `#modal-close-btn`
  - `#login-modal-close-btn`
- 在 `www/download.js` 中新增：
  - `bindEnterShortcut(...)`
  - `bindModalDismiss(...)`
  - `bindEventHandlers()`
- 统一在 `init()` 中完成事件绑定和页面初始化。

## 保持不变的边界

- 保留 `window.DownloadPage` 现有导出，避免误伤现有脚本、调试调用和潜在外部依赖。
- 不修改下载任务流、游客会话流和登录鉴权接口。
- 不调整页面 URL 与服务端路由。

## 验证

- `node --check www/download.js`
- `python -m unittest tests.test_frontend_build_setup_unittest tests.test_frontend_session_contract_unittest -v`
- `node build.js`
