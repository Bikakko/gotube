# 任务 12 工作日志：Cookie 诊断面板

## 背景

任务 10 验收期间出现过 Bilibili、X/Twitter、YouTube 下载异常，最终定位到 Cookie 运行源和上传内容状态不透明。任务 12 的目标不是增强平台解析能力，而是在管理后台提供非敏感诊断信息，让管理员能判断当前 `data/cookies.txt` 是否具备各平台常见登录字段。

## 修复内容

- 在 `server.cookie_store` 增加 `diagnose_cookie_content()`：
  - 解析 Netscape Cookie 文本中的域名和 cookie 名称。
  - 按平台检查关键字段：
    - Bilibili：`SESSDATA`、`bili_jct`、`DedeUserID`
    - X/Twitter：`auth_token`、`ct0`
    - YouTube：`SAPISID`、`__Secure-1PSID`、`__Secure-3PSID`
  - 返回 `has_required`、`present`、`missing`、`domains`。
  - 不返回 cookie 值，避免敏感信息进入 API 响应、日志或前端 DOM。
- 在 `GET /admin/api/cookies/status` 响应中增加 `diagnostics` 字段：
  - 无 Cookie 文件时也返回空诊断结构，前端可稳定渲染。
  - 有 Cookie 文件时基于当前运行期 `data/cookies.txt` 诊断。
- 在管理后台 Cookie 弹窗中增加“平台登录态诊断”：
  - 展示 Bilibili、X/Twitter、YouTube 三个平台是否完整。
  - 展示已有字段、缺失字段和匹配域名。
  - 前端展示前对字段和域名做 HTML 转义。

## 回归测试

新增 `tests/test_cookie_diagnostics_unittest.py`，覆盖：

- 诊断结果显示已存在字段和缺失字段。
- 诊断结果不包含 cookie 值。
- 各平台关键字段完整时标记为完整。
- 格式错误的行会被忽略，不影响诊断结构。

已运行：

```powershell
.\venv\Scripts\python.exe -m unittest tests.test_cookie_diagnostics_unittest tests.test_cookie_store_unittest
node --check www\admin\js\cookies.js
.\venv\Scripts\python.exe -m py_compile server\cookie_store.py server\admin_api.py
```

结果均通过。

## 后续注意

- 诊断字段是“常见登录态关键字段”，不是平台成功下载的绝对保证。平台风控、IP、账号状态、yt-dlp 版本仍可能影响下载。
- 个人用户 Cookie 上传仍保持低优先级，未纳入本任务。
