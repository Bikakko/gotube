# 2026-05-01 任务 5：`shared/ + home/` 第一阶段实际迁移

## 目标

按照 `4.7.1` 预案，先完成最稳的一步：

- 共享资源迁入 `www/shared/`
- 首页资源迁入 `www/home/`
- 保持正式访问 URL 不变

## 本次迁移内容

### 共享资源

- `www/common.js` -> `www/shared/common.js`
- `www/vendor/three.core.min.js` -> `www/shared/vendor/three.core.min.js`
- `www/vendor/three.module.min.js` -> `www/shared/vendor/three.module.min.js`
- `www/favicon.jpg` -> `www/shared/images/favicon.jpg`

### 首页资源

- `www/index.html` -> `www/home/index.html`
- `www/index.js` -> `www/home/page.js`
- `www/index.css` -> `www/home/page.css`
- `www/moon.png` -> `www/home/moon.png`
- `www/secret-entry-placeholder.gif` -> `www/home/secret-entry-placeholder.gif`

## 同步修改

- `server/main.py`
  - 根页面入口改为读取 `home/index.html`
  - 保护性静态文件白名单同步加入 `home/index.html`
- 页面资源引用同步更新：
  - 首页改用 `/static/home/...`
  - favicon / common.js / Three.js 改用 `/static/shared/...`
- 实验页 `visual-lab-c.*` 的共享资源引用同步到新位置

## 测试更新

- `tests/test_frontend_build_setup_unittest.py`
- `tests/test_frontend_session_contract_unittest.py`
- `tests/test_home_gallery_frontend_unittest.py`

更新内容：

- 首页路径常量指向 `www/home/...`
- 共享脚本常量指向 `www/shared/common.js`
- 样式与脚本断言对齐当前正式首页结构

## 验证

- `node --check www/home/page.js`
- `python -m unittest tests.test_frontend_build_setup_unittest tests.test_frontend_session_contract_unittest tests.test_home_gallery_frontend_unittest -v`
- `python -m py_compile server/main.py`
- `node build.js`
