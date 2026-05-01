# 2026-05-01 任务 7：`watch/ + labs/` 第三阶段实际迁移

## 目标

在不改变正式播放页 URL 的前提下，将播放页和实验页从 `www/` 根层级迁移到各自目录。

## 本次迁移内容

### 播放页

- `www/watch.html` -> `www/watch/index.html`

### 实验页

- `www/visual-lab-c.html` -> `www/labs/visual-lab-c.html`
- `www/visual-lab-c.css` -> `www/labs/visual-lab-c.css`
- `www/visual-lab-c.js` -> `www/labs/visual-lab-c.js`

## 同步修改

- `server/main.py`
  - `/watch` HTML 入口改为读取 `watch/index.html`
  - 注释同步更新到新结构
- 实验页资源引用更新为：
  - `/static/labs/visual-lab-c.css?v={{ASSET_VERSION}}`
  - `/static/labs/visual-lab-c.js?v={{ASSET_VERSION}}`

## 保持不变

- 正式播放页访问 URL 仍然是 `/watch?v=...`
- `/watch.html` 依旧直接返回 404
- 实验页仍然只是实验资产，不作为正式业务入口

## 测试更新

- `tests/test_frontend_build_setup_unittest.py`
- `tests/test_admin_modals_frontend_unittest.py`

## 验证

- `node --check www/labs/visual-lab-c.js`
- `python -m unittest tests.test_frontend_build_setup_unittest tests.test_frontend_session_contract_unittest tests.test_home_gallery_frontend_unittest tests.test_admin_modals_frontend_unittest -v`
- `python -m py_compile server/main.py`
- `node build.js`
