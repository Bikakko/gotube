# 2026-05-01 任务 4：前端模块边界收口

## 范围

- 任务来源：`4.6.0` 计划任务 4
- 目标文件：
  - `www/common.js`
  - `www/download.js`
  - `www/index.js`
  - `docs/superpowers/specs/2026-05-01-frontend-module-boundaries.md`
  - `tests/test_frontend_build_setup_unittest.py`

## 本轮调整

1. 建立统一全局命名空间
   - 新增 `window.GoTube = window.GoTube || {}`
   - 将现有 `window.GoTubeSession` 统一别名为 `window.GoTube.session`

2. 收口共享能力出口
   - 在 `window.GoTube.utils` 下统一暴露：
     - DOM 工具
     - 格式化工具
     - API 封装
   - 新增 `window.GoTube.resolveHiddenPath(...)` 作为弱隐藏路径推断入口

3. 下载页接入统一边界
   - 下载页不再直接依赖裸露的 `window.GoTubeSession`
   - 改为优先从 `window.GoTube.session` 与 `window.GoTube.resolveHiddenPath(...)` 取共享能力

4. 首页模块显式加入命名空间
   - 首页 ES Module 继续保留
   - 首页在 `window.GoTube.home` 下暴露稳定入口：
     - `ensureScene`
     - `closeGalleryModal`

5. 补边界说明文档
   - 明确：
     - 首页可继续独立使用 ES Module
     - 下载页/后台暂不强制迁移 module
     - 共享能力必须经由 `window.GoTube` 暴露

## 验证

- `python -m unittest tests.test_frontend_build_setup_unittest -v`
- `node --check www/common.js`
- `node --check www/download.js`
- `node --check www/index.js`
- `node build.js`

结果：

- 前端构建测试 `8` 项通过
- 三个前端脚本语法检查通过
- `www_dist` 构建成功

## 备注

- 本轮没有推进 TypeScript，也没有把下载页/后台整体迁移到 ES Module。
- 目标只是先把共享边界收口，避免后续继续在各脚本之间直接扩散局部变量依赖。
