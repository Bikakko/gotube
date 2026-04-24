# GoTube Desktop 0.1.0 设计说明

## 定位

GoTube Desktop 是从 GoTube Web 版中抽取下载核心能力的 Windows 单机版。它不是 Web 服务的完整打包，也不继承多用户平台能力。

桌面版只服务本机当前用户，目标是提供一个可双击启动、可配置保存位置、可管理 Cookie 与下载工具链的本地视频下载器。

## 保留能力

- 输入视频链接并创建下载任务。
- 显示任务状态、进度、速度、错误信息。
- 设置本机视频保存目录。
- 下载完成后播放文件或打开所在目录。
- 手动导入 `cookies.txt` 或粘贴 Netscape 格式 Cookie。
- 从本机浏览器导入 Cookie，优先支持 Edge / Chrome。
- 检测 `yt-dlp` 版本并支持升级。
- 检测 `ffmpeg` 是否可用，并允许用户选择 `ffmpeg.exe` 所在路径。
- 显示最近运行日志和下载错误。

## 删除能力

- 用户系统。
- 管理员后台。
- 注册、邀请码、角色、容量限制。
- 多用户视频库。
- 游客临时目录。
- 分享链接。
- 服务端部署脚本、Nginx、systemd。
- 面向公网服务的安全策略。

## 技术路线

第一版采用 Python 下载核心 + pywebview 桌面壳。

- Python 负责配置、下载、Cookie、工具检测与日志。
- pywebview 负责 Windows 桌面窗口。
- 前端仍使用 HTML / CSS / JS，但只作为本地桌面 UI。
- 打包使用 PyInstaller，生成 Windows 可执行文件。

暂不使用 C++ 全量重写。C++ 可作为后续原生壳候选，但下载核心仍应继续依赖 `yt-dlp`，避免自行维护视频平台解析逻辑。

## 目录结构

桌面版代码放在独立目录，避免污染 Web 服务主线。

```text
desktop/
  app.py
  core/
    config.py
    cookies.py
    downloader.py
    tasks.py
    tools.py
    logs.py
  ui/
    index.html
    app.js
    style.css
  packaging/
    gotube-desktop.spec
```

测试放在 `tests/desktop/`。

## 配置模型

配置存放在用户本机应用数据目录：

```text
%APPDATA%/GoTubeDesktop/config.json
```

第一版配置项：

- `download_dir`
- `cookies_file`
- `browser_cookie_source`
- `ffmpeg_path`
- `ytdlp_update_policy`
- `last_window_size`

默认下载目录：

```text
%USERPROFILE%/Downloads/GoTube
```

## Cookie 方案

第一版提供两种方式：

1. 手动导入 Cookie。
   - 上传 `cookies.txt`。
   - 粘贴 Netscape 格式文本。
   - 保存到 `%APPDATA%/GoTubeDesktop/cookies.txt`。

2. 从浏览器导入 Cookie。
   - 用户主动点击导入。
   - 支持 Edge / Chrome 优先。
   - 调用 `yt-dlp` 的浏览器 Cookie 能力或兼容的本地读取逻辑。
   - 不做自动网页登录。
   - 不保存浏览器密码，不读取无关站点数据。

失败时给出明确提示，例如浏览器正在运行、浏览器数据库被锁、系统解密失败、未找到浏览器配置。

## 工具管理

`yt-dlp`：

- 显示当前版本。
- 支持检查更新。
- 支持升级到最新版本。
- 升级失败时保留旧版本。

`ffmpeg`：

- 检测 PATH 中是否可用。
- 检测用户手动选择的 `ffmpeg.exe`。
- 第一版不做自动下载和自动升级。

## 下载核心

桌面版下载核心应尽量独立于 Web 版的用户、数据库、WebSocket 和队列模型。

第一版只需要本机任务队列：

- pending
- running
- completed
- failed
- canceled

任务状态只保存在内存中。下载完成文件保留在下载目录。是否持久化任务历史放到后续版本。

## UI 结构

第一版 UI 只保留必要页面：

- 下载页：输入链接、任务列表、打开文件、打开目录。
- 设置页：下载目录、Cookie、yt-dlp、ffmpeg。
- 日志页：最近日志和错误。

UI 风格可以延续 GoTube 月夜玻璃感，但桌面工具应保持信息清晰，不引入复杂背景特效。

## 打包边界

第一版打包产物目标：

```text
GoTubeDesktop.exe
```

打包内容：

- Python 运行时。
- 桌面版 Python 代码。
- 桌面 UI 静态文件。
- 必要依赖。

不默认内置大型 `ffmpeg` 二进制。是否随包分发 `yt-dlp.exe` 或使用 Python 包内 `yt_dlp`，在实现阶段以打包可维护性为准。

## 非目标

- 不做公网服务。
- 不做多用户。
- 不做自动登录平台账号。
- 不做分享链接。
- 不做完整媒体库管理。
- 不做 C++ 全量重写。
- 不做 FFmpeg 自动安装。

## 验收标准

- Windows 上双击启动桌面窗口。
- 可设置下载目录并持久保存。
- 可提交链接下载并看到进度。
- 下载完成后可打开文件或所在目录。
- 手动 Cookie 可被下载任务使用。
- 浏览器 Cookie 导入失败时有明确错误提示。
- `yt-dlp` 可检测版本并触发升级。
- `ffmpeg` 可检测并允许手动选择路径。
- PyInstaller 可生成可启动的 `.exe`。
