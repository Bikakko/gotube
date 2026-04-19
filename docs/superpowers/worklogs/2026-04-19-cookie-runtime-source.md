# Cookie 运行源修复日志

## 背景

手工验收中发现：管理页上传了 Cookie 后，删除根目录 `cookies.txt` 又会出现残缺 Cookie；B 站、Twitter、YouTube 下载能力表现不稳定。排查后确认 Cookie 来源存在不一致：

- 管理页上传写入 `data/cookies.txt`。
- 上传后热重载会让当前进程使用 `data/cookies.txt`。
- 服务重启时 `Downloader()` 仍从 `.env` 的 `GOTUBE_COOKIES_FILE=./cookies.txt` 读取根目录 Cookie。
- 管理页状态又优先显示 `data/cookies.txt`，导致“页面显示上传 Cookie 生效，下载器实际可能使用根目录 Cookie”。

## 修复策略

- 新增 `server/cookie_store.py`，统一 Cookie 路径决策。
- `data/cookies.txt` 作为唯一运行时 Cookie 源。
- `.env` 指向的旧 Cookie 只作为首次兼容导入来源：当 `data/cookies.txt` 不存在且未执行过导入检查时，复制到 `data/cookies.txt`。
- 删除上传 Cookie 后写入导入标记，后续不再自动回退到 `.env` 根目录 Cookie。
- `Downloader()` 默认从统一运行源读取 Cookie。
- 管理 API 的状态、上传、删除逻辑改为同一套运行源语义。
- 管理页删除确认文案同步为“不自动回退根目录 cookies.txt”。

## 验证记录

已运行：

```powershell
venv\Scripts\python.exe -m unittest tests.test_cookie_store_unittest tests.test_downloader_error_messages_unittest tests.test_frontend_session_contract_unittest
venv\Scripts\python.exe -m py_compile server\cookie_store.py server\downloader.py server\admin_api.py
node --check www\admin\js\cookies.js
git diff --check
```

当前项目解析结果：

```text
runtime= D:\工作区\gotube.dev\gotube\data\cookies.txt
status= D:\工作区\gotube.dev\gotube\data\cookies.txt
```

`git diff --check` 仅有 Windows 换行提示，无空白错误。

## 后续注意

- 根目录 `cookies.txt` 不再作为运行期回退来源；后续建议从 `.env.example` 或管理页文案中逐步弱化这个配置。
- 如果需要完全清空 Cookie，在管理页删除上传 Cookie 即可；删除后下载器不再自动使用根目录残缺 Cookie。
