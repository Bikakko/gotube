# 2026-05-01 任务 2：首页初始化收口

## 目标

将首页顶层散落的初始化逻辑收口到显式入口，明确页面行为、模态交互与场景生命周期的组织边界。

## 本次改动

- 在 `www/index.js` 中新增：
  - `bindSecretEntryImage()`
  - `bindModalEvents()`
  - `bindSceneLifecycle()`
  - `bootstrapHomePage()`
- 将原先分散在顶层的：
  - 月亮入口图片 fallback
  - 模态关闭 / 翻页事件
  - `pageshow` 场景恢复
  - `beforeunload` 场景释放
  - 相册加载启动
  统一收口进 `bootstrapHomePage()`
- 对外共享边界新增：
  - `window.GoTube.home.bootstrap`

## 保持不变的边界

- 不改变首页 Three.js 场景参数与视觉表现
- 不改变月亮隐藏入口行为
- 不改变相册 API 与模态交互语义

## 验证

- `node --check www/index.js`
- `python -m unittest tests.test_frontend_build_setup_unittest -v`
- `node build.js`
