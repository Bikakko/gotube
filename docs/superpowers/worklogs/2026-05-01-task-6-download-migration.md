# 2026-05-01 任务 6：`download/` 第二阶段实际迁移

## 目标

在不改变下载页公开入口 URL 的前提下，将下载页资源从 `www/` 根层级迁移到独立目录。

## 本次迁移内容

- `www/download.html` -> `www/download/index.html`
- `www/download.js` -> `www/download/page.js`

## 同步修改

- `server/main.py`
  - 下载页入口改为读取 `download/index.html`
  - 保护性静态文件白名单同步加入 `download/index.html`
- 下载页 HTML 的脚本引用改为：
  - `/static/download/page.js?v={{ASSET_VERSION}}`
- 前端测试同步更新：
  - `tests/test_frontend_build_setup_unittest.py`
  - `tests/test_frontend_session_contract_unittest.py`

## 保持不变

- 下载页公开访问入口仍然是 `/<hidden>`
- `window.GoTube.download` 边界不变
- 下载、登录、注册、游客会话、视频库逻辑不做行为变更

## 验证

- `node --check www/download/page.js`
- `python -m unittest tests.test_frontend_build_setup_unittest tests.test_frontend_session_contract_unittest tests.test_home_gallery_frontend_unittest -v`
- `python -m py_compile server/main.py`
- `node build.js`
