# 2026-05-01 任务 3：共享与页面私有逻辑分层

## 目标

在不破坏现有页面行为的前提下，继续收紧共享边界，让页面私有能力优先挂载到 `window.GoTube` 命名空间，而不是继续扩散新的顶层全局对象。

## 本次改动

- 在 `www/download.js` 中新增：
  - `window.GoTube.download`
  - `const downloadPage = goTube.download`
- 将下载页现有对外可调用能力挂载到：
  - `window.GoTube.download.bootstrap`
  - 以及对应页面动作方法
- 保留：
  - `window.DownloadPage = downloadPage`

## 兼容策略

- 旧别名 `window.DownloadPage` 暂时不删除，避免误伤调试调用和潜在外部脚本。
- 新 HTML 和新脚本不再继续依赖 `window.DownloadPage`。
- 后续若继续收口，可以在确认无外部依赖后移除兼容别名。

## 文档更新

- 更新 `2026-05-01-frontend-module-boundaries.md`
- 明确 `window.GoTube.home` 与 `window.GoTube.download` 的职责边界

## 验证

- `node --check www/download.js`
- `python -m unittest tests.test_frontend_build_setup_unittest -v`
- `node build.js`
