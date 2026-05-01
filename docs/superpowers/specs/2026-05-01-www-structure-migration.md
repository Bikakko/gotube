# 2026-05-01 `www/` 目录结构重组预案

## 背景

当前前端资源分布在单个 `www/` 目录中，存在以下问题：

- 首页、下载页、播放页、后台页与共享资源平铺混放。
- 首页资源与实验页资源同层级存放，页面边界不清晰。
- 服务端 `server/main.py` 直接按固定文件路径读取：
  - `index.html`
  - `download.html`
  - `admin/admin.html`
  - `watch.html`
- 构建脚本 `build.js` 直接从 `www/` 递归复制到 `www_dist/`，未体现页面与共享资源层次。

## 目标

下一阶段通过目录重组达到以下目的：

1. 页面私有资源与共享资源分离。
2. 首页、下载页、播放页、后台各自拥有稳定目录边界。
3. 为后续模块化、类型化和样式收敛提供更清晰的物理结构。
4. 在迁移过程中尽量不改变最终公开 URL。

## 推荐目标结构

```text
www/
  shared/
    common.js
    vendor/
    images/
      favicon.jpg
  home/
    index.html
    page.js
    page.css
    moon.png
    secret-entry-placeholder.gif
  download/
    index.html
    page.js
  watch/
    index.html
  admin/
    index.html
    css/
    js/
  labs/
    visual-lab-c.html
    visual-lab-c.css
    visual-lab-c.js
```

## URL 兼容策略

目录重组只改变仓库内的物理结构，不改变最终访问路径：

- `/` 仍提供首页
- `/<hidden>` 仍提供下载页
- `/<hidden>/admin` 仍提供后台页
- `/watch` 仍提供播放页
- `/static/...` 仍作为统一静态资源前缀

实现方式：

- `server/main.py` 的页面读取逻辑改为新物理路径映射
- `StaticFiles` 继续挂载重组后的 `www` / `www_dist`
- 页面内资源引用统一走 `/static/...`

## 分阶段迁移建议

### 阶段 1：先搬共享资源与首页

优先级最高：

- `common.js` -> `shared/common.js`
- `vendor/` -> `shared/vendor/`
- `favicon.jpg` -> `shared/images/favicon.jpg`
- `index.html` / `index.js` / `index.css` -> `home/`

原因：

- 首页已经有明确的 `index.js` / `index.css` 组合。
- 首页与共享资源的分离最容易建立模板。

### 阶段 2：下载页目录化

- `download.html` -> `download/index.html`
- `download.js` -> `download/page.js`

要求：

- 保持 `window.GoTube.download` 边界不变
- 先迁物理位置，再考虑进一步拆分状态、鉴权、任务、视频库子模块

### 阶段 3：播放页与实验页归位

- `watch.html` -> `watch/index.html`
- `visual-lab-c.*` -> `labs/`

说明：

- 实验页不应继续与正式首页平铺在根层级。
- `labs/` 只承载实验资产，不参与正式服务入口。

### 阶段 4：后台页入口统一

- `admin/admin.html` -> `admin/index.html`
- 保留 `admin/css/`、`admin/js/`

说明：

- 后台本身已经相对分层，不需要先拆内部结构。
- 当前任务重点只是统一入口命名和页面根目录习惯。

## 服务端改造点

需要修改的关键位置：

- `server/main.py`
  - `_serve_html(...)` 的目标文件路径映射
  - 根页面、下载页、后台页、播放页的入口路径
  - 保护性静态路由判断中的文件名白名单

## 构建脚本改造点

需要修改的关键位置：

- `build.js`
  - 继续从 `www/` 根递归构建即可，不强制立即改逻辑
  - 但应补文档说明：构建脚本依赖物理目录重组后的新路径

说明：

- `build.js` 当前是“递归式复制 + 压缩”，结构重组后仍能工作。
- 真正需要更新的是页面内资源路径和服务端入口映射，不是构建算法本身。

## 暂不做的事

- 本轮不引入前端 bundler。
- 本轮不引入 TypeScript。
- 本轮不把后台整体改成 ES Module。
- 本轮不重写 `/static` 路径策略。

## 迁移验收标准

1. 所有正式页面入口路径保持不变。
2. `node build.js` 在新结构下无额外特判即可通过。
3. `server/main.py` 能正确读取新位置的 HTML 文件。
4. 首页、下载页、后台页各自私有资源不再与共享资源平铺混放。
