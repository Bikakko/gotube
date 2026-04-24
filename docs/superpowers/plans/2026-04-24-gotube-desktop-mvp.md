# GoTube Desktop 0.1.0 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 构建 Windows 单机桌面版 MVP，抽取 GoTube 的下载核心能力，支持本地保存目录、Cookie 管理、浏览器 Cookie 导入、yt-dlp/ffmpeg 管理。

**架构：** 桌面版代码独立放在 `desktop/`，不复用 Web 版多用户、数据库、后台和分享模型。Python 核心提供配置、任务、下载、工具和日志能力，pywebview 提供桌面窗口，前端通过 pywebview API 调用本地 Python。

**技术栈：** Python、yt-dlp、pywebview、PyInstaller、HTML/CSS/JS、unittest。

---

## 文件结构

- 创建：`desktop/app.py`，桌面入口，启动 pywebview。
- 创建：`desktop/core/config.py`，本地配置读写。
- 创建：`desktop/core/tools.py`，yt-dlp 与 ffmpeg 检测、升级、路径配置。
- 创建：`desktop/core/cookies.py`，手动 Cookie 保存、格式校验、浏览器 Cookie 导入。
- 创建：`desktop/core/tasks.py`，单机任务状态模型。
- 创建：`desktop/core/downloader.py`，单机下载执行器。
- 创建：`desktop/core/logs.py`，桌面版日志读写。
- 创建：`desktop/ui/index.html`，桌面 UI 入口。
- 创建：`desktop/ui/app.js`，桌面 UI 交互。
- 创建：`desktop/ui/style.css`，桌面 UI 样式。
- 创建：`desktop/packaging/gotube-desktop.spec`，PyInstaller 打包配置。
- 创建：`tests/desktop/test_config_unittest.py`。
- 创建：`tests/desktop/test_tools_unittest.py`。
- 创建：`tests/desktop/test_cookies_unittest.py`。
- 创建：`tests/desktop/test_tasks_unittest.py`。
- 创建：`tests/desktop/test_downloader_unittest.py`。
- 修改：`pyproject.toml` 或依赖文件，补充桌面版可选依赖。
- 修改：`.gitignore`，忽略桌面构建产物。

## 任务 1：本地配置核心

**文件：**
- 创建：`desktop/core/config.py`
- 测试：`tests/desktop/test_config_unittest.py`

- [ ] **步骤 1：编写失败测试**

```python
def test_desktop_config_uses_default_download_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "User"))
    from desktop.core.config import DesktopConfigStore

    store = DesktopConfigStore()
    config = store.load()

    assert str(config.download_dir).endswith("Downloads\\GoTube")
```

- [ ] **步骤 2：运行测试验证失败**

运行：`python -m unittest tests.desktop.test_config_unittest`

预期：导入 `desktop.core.config` 失败。

- [ ] **步骤 3：实现配置读写**

实现 `DesktopConfig` 与 `DesktopConfigStore`：

```python
@dataclass
class DesktopConfig:
    download_dir: Path
    cookies_file: Path | None = None
    ffmpeg_path: Path | None = None
    browser_cookie_source: str | None = None
```

配置文件路径为 `%APPDATA%/GoTubeDesktop/config.json`。

- [ ] **步骤 4：运行测试验证通过**

运行：`python -m unittest tests.desktop.test_config_unittest`

- [ ] **步骤 5：提交**

```bash
git add desktop/core/config.py tests/desktop/test_config_unittest.py
git commit -m "feat(desktop): 增加本地配置核心"
```

## 任务 2：工具检测与升级入口

**文件：**
- 创建：`desktop/core/tools.py`
- 测试：`tests/desktop/test_tools_unittest.py`

- [ ] **步骤 1：编写失败测试**

```python
def test_ffmpeg_detection_accepts_configured_executable(tmp_path):
    ffmpeg = tmp_path / "ffmpeg.exe"
    ffmpeg.write_text("", encoding="utf-8")
    from desktop.core.tools import detect_ffmpeg

    result = detect_ffmpeg(configured_path=ffmpeg)

    assert result.available is True
    assert result.path == ffmpeg
```

- [ ] **步骤 2：运行测试验证失败**

运行：`python -m unittest tests.desktop.test_tools_unittest`

- [ ] **步骤 3：实现工具检测**

实现：

- `detect_ytdlp()`
- `upgrade_ytdlp()`
- `detect_ffmpeg(configured_path=None)`

`upgrade_ytdlp()` 第一版调用当前 Python 环境的 pip 升级 `yt-dlp`，失败时返回结构化错误。

- [ ] **步骤 4：运行测试验证通过**

运行：`python -m unittest tests.desktop.test_tools_unittest`

- [ ] **步骤 5：提交**

```bash
git add desktop/core/tools.py tests/desktop/test_tools_unittest.py
git commit -m "feat(desktop): 增加下载工具检测"
```

## 任务 3：Cookie 管理

**文件：**
- 创建：`desktop/core/cookies.py`
- 测试：`tests/desktop/test_cookies_unittest.py`

- [ ] **步骤 1：编写失败测试**

```python
def test_save_manual_cookie_rejects_invalid_format(tmp_path):
    from desktop.core.cookies import DesktopCookieStore

    store = DesktopCookieStore(tmp_path)

    result = store.save_manual_cookie("not a netscape cookie file")

    assert result.ok is False
```

- [ ] **步骤 2：运行测试验证失败**

运行：`python -m unittest tests.desktop.test_cookies_unittest`

- [ ] **步骤 3：实现手动 Cookie 保存**

复用 Web 版 Cookie 校验思想，桌面版只保存到 `%APPDATA%/GoTubeDesktop/cookies.txt`。

实现：

- `save_manual_cookie(content)`
- `get_cookie_file()`
- `delete_cookie_file()`
- `diagnose_cookie_content(content)`

- [ ] **步骤 4：实现浏览器 Cookie 导入接口**

先实现接口壳，不自动登录：

```python
def import_from_browser(browser: str) -> CookieImportResult:
    ...
```

第一版允许返回明确失败信息，例如浏览器不支持、Cookie 数据库被锁、导入失败。后续任务再接 `yt-dlp` 的浏览器 Cookie 能力。

- [ ] **步骤 5：运行测试验证通过**

运行：`python -m unittest tests.desktop.test_cookies_unittest`

- [ ] **步骤 6：提交**

```bash
git add desktop/core/cookies.py tests/desktop/test_cookies_unittest.py
git commit -m "feat(desktop): 增加本地 Cookie 管理"
```

## 任务 4：任务模型与下载核心

**文件：**
- 创建：`desktop/core/tasks.py`
- 创建：`desktop/core/downloader.py`
- 测试：`tests/desktop/test_tasks_unittest.py`
- 测试：`tests/desktop/test_downloader_unittest.py`

- [ ] **步骤 1：编写任务状态测试**

```python
def test_task_transitions_from_pending_to_running():
    from desktop.core.tasks import DesktopTask

    task = DesktopTask.create(url="https://example.test/video")
    task.mark_running()

    assert task.status == "running"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`python -m unittest tests.desktop.test_tasks_unittest`

- [ ] **步骤 3：实现任务模型**

实现状态：

- `pending`
- `running`
- `completed`
- `failed`
- `canceled`

- [ ] **步骤 4：编写下载器参数测试**

```python
def test_downloader_builds_ytdlp_options_with_download_dir(tmp_path):
    from desktop.core.downloader import DesktopDownloader

    downloader = DesktopDownloader(download_dir=tmp_path)
    opts = downloader.build_ytdlp_options()

    assert str(tmp_path) in opts["outtmpl"]
```

- [ ] **步骤 5：实现最小下载器**

实现：

- `build_ytdlp_options()`
- `download(url, task_id)`
- 进度回调
- Cookie 文件注入
- ffmpeg 路径注入

不接入 Web 版用户模型、数据库、分享逻辑。

- [ ] **步骤 6：运行测试验证通过**

运行：

```bash
python -m unittest tests.desktop.test_tasks_unittest tests.desktop.test_downloader_unittest
```

- [ ] **步骤 7：提交**

```bash
git add desktop/core/tasks.py desktop/core/downloader.py tests/desktop/test_tasks_unittest.py tests/desktop/test_downloader_unittest.py
git commit -m "feat(desktop): 增加单机下载核心"
```

## 任务 5：桌面 API 与 UI

**文件：**
- 创建：`desktop/app.py`
- 创建：`desktop/ui/index.html`
- 创建：`desktop/ui/app.js`
- 创建：`desktop/ui/style.css`

- [ ] **步骤 1：实现 pywebview API 类**

创建 `DesktopApi`，暴露：

- `get_config()`
- `set_download_dir(path)`
- `create_download(url)`
- `get_tasks()`
- `save_cookie(content)`
- `import_browser_cookie(browser)`
- `detect_tools()`
- `upgrade_ytdlp()`
- `get_logs()`

- [ ] **步骤 2：实现 UI 骨架**

UI 三个区块：

- 下载
- 设置
- 日志

下载页包含链接输入、任务列表、打开文件夹按钮。

- [ ] **步骤 3：运行桌面入口**

运行：`python -m desktop.app`

预期：打开 pywebview 窗口，页面能调用 `get_config()`。

- [ ] **步骤 4：提交**

```bash
git add desktop/app.py desktop/ui/index.html desktop/ui/app.js desktop/ui/style.css
git commit -m "feat(desktop): 增加桌面 UI 骨架"
```

## 任务 6：打包配置

**文件：**
- 创建：`desktop/packaging/gotube-desktop.spec`
- 修改：`.gitignore`
- 修改：依赖文件

- [ ] **步骤 1：补依赖**

增加桌面版依赖：

- `pywebview`
- `pyinstaller`

如果项目不希望默认安装桌面依赖，使用独立 `requirements-desktop.txt`。

- [ ] **步骤 2：补 PyInstaller spec**

spec 需要包含：

- `desktop/ui/`
- `VERSION`
- 必要 Python 包

- [ ] **步骤 3：补忽略规则**

忽略：

```text
dist/
build/
*.spec.bak
```

- [ ] **步骤 4：执行打包冒烟测试**

运行：

```bash
pyinstaller desktop/packaging/gotube-desktop.spec
```

预期：生成 `dist/GoTubeDesktop/GoTubeDesktop.exe`。

- [ ] **步骤 5：提交**

```bash
git add desktop/packaging/gotube-desktop.spec requirements-desktop.txt .gitignore
git commit -m "build(desktop): 增加 Windows 打包配置"
```

## 任务 7：收尾验收

**文件：**
- 创建：`docs/ops/desktop-windows.md`

- [ ] **步骤 1：写 Windows 桌面版使用说明**

包含：

- 首次启动。
- 设置下载目录。
- 导入 Cookie。
- 检测 yt-dlp。
- 检测 ffmpeg。
- 打包命令。

- [ ] **步骤 2：跑完整测试**

运行：

```bash
python -m unittest tests.desktop.test_config_unittest tests.desktop.test_tools_unittest tests.desktop.test_cookies_unittest tests.desktop.test_tasks_unittest tests.desktop.test_downloader_unittest
```

- [ ] **步骤 3：手工验收**

检查：

- 桌面窗口能打开。
- 下载目录可保存。
- Cookie 可导入。
- yt-dlp 可检测。
- ffmpeg 可检测。
- 打包产物可启动。

- [ ] **步骤 4：提交**

```bash
git add docs/ops/desktop-windows.md
git commit -m "docs(desktop): 增加 Windows 桌面版说明"
```

## 自检

- 规格中的保留能力均有对应任务。
- 多用户、分享、后台、邀请码未进入桌面版范围。
- Cookie 自动获取只做到用户主动导入，不做自动登录。
- FFmpeg 第一版只做检测和手动选择，不做自动安装。
- 每个核心模块均有测试任务。
