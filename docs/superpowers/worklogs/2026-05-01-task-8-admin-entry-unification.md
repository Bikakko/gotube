# 2026-05-01 任务 8：后台入口统一为 `admin/index.html`

## 目标

完成 `4.7.1` 目录重组的最后一步：将后台入口文件统一为 `www/admin/index.html`，与首页、下载页、播放页的入口命名风格保持一致。

## 本次迁移内容

- `www/admin/admin.html` -> `www/admin/index.html`

## 同步修改

- `server/main.py`
  - 后台入口改为读取 `admin/index.html`
  - 保护性静态文件白名单加入 `admin/index.html`
- 测试同步更新：
  - `tests/test_frontend_build_setup_unittest.py`
  - `tests/test_admin_management_unittest.py`

## 保持不变

- 正式后台访问 URL 仍然是 `/<hidden>/admin`
- 后台 CSS / JS 目录结构不变
- 后台鉴权和页面行为不变

## 验证

- `python -m unittest tests.test_frontend_build_setup_unittest tests.test_admin_management_unittest tests.test_admin_modals_frontend_unittest -v`
- `python -m py_compile server/main.py`
- `node build.js`
