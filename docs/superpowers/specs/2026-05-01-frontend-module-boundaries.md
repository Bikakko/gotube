# 2026-05-01 前端模块边界说明

## 目标

在不推翻现有前端加载方式的前提下，为共享能力建立稳定边界，减少首页 ES Module 与下载页/后台全局脚本混用带来的扩散风险。

## 当前约束

- `index.js` 继续使用 ES Module。
- `download.js`、`common.js`、后台脚本暂不强制迁移为 ES Module。
- 共享能力统一通过 `window.GoTube` 命名空间暴露。

## 命名空间约定

### `window.GoTube.session`

当前由 `window.GoTubeSession` 承载，统一别名挂到：

```javascript
window.GoTube.session = window.GoTubeSession;
```

### `window.GoTube.utils`

允许暴露的共享工具：

- `$`
- `$$`
- `el`
- `formatBytes`
- `formatSpeed`
- `formatETA`
- `escapeHtml`
- `extractSource`
- `formatRole`
- `getApiBase`
- `apiFetch`

### `window.GoTube.resolveHiddenPath(...)`

统一隐藏路径解析入口：

```javascript
window.GoTube.resolveHiddenPath(pathname, injectedHiddenPath)
```

用于收敛下载页和后台对弱隐藏入口路径的推断逻辑。

### `window.GoTube.home`

首页模块可在该对象下暴露少量稳定入口，例如：

- `ensureScene`
- `closeGalleryModal`

不要求把首页 Three.js 内部状态全部泄漏到全局。

## 不做的事

- 本轮不把下载页和后台整体迁移到 ES Module。
- 本轮不引入 bundler 级别的模块重写。
- 本轮不做 TypeScript 化。

## 后续演进方向

1. 先保持 `window.GoTube` 作为跨脚本稳定边界。
2. 后续若迁移下载页/后台到 ES Module，优先围绕该边界做收缩，而不是直接跨文件互相取局部变量。
3. TypeScript 化时，先为 `window.GoTube` 定义全局类型，再逐步替换脚本内部实现。
