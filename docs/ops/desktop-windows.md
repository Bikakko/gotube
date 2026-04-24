# GoTube Desktop Windows MVP 使用说明

本文档面向 GoTube Desktop 0.1.0 MVP。桌面版只保留单机下载能力，不接入多用户视频库、邀请码、分享链接、后台管理等 Web 服务功能。

## 运行环境

- Windows 10 或 Windows 11。
- Python 3.11 及以上版本。
- 可访问目标视频网站的网络环境。
- 推荐准备可用的 `ffmpeg`，用于合并音视频分离格式。

## 安装依赖

在项目根目录执行：

```powershell
python -m venv .venv-desktop
.\.venv-desktop\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r requirements-desktop.txt
```

`requirements-desktop.txt` 会安装桌面壳、打包工具和下载核心依赖，其中包括：

- `pywebview`：提供桌面窗口。
- `pyinstaller`：生成 Windows 可执行文件。
- `yt-dlp`：执行视频解析和下载。

## 开发模式启动

在项目根目录执行：

```powershell
python -m desktop.app
```

首次启动后，桌面版会在当前 Windows 用户目录下创建本地配置。默认视频保存目录为：

```text
%USERPROFILE%\Downloads\GoTube
```

该配置只影响桌面版，不会读取或修改服务器 `.env`。

## 基础使用

1. 打开桌面窗口。
2. 在下载输入框粘贴视频链接。
3. 点击下载。
4. 文件会保存到当前设置的视频保存目录。

当前 MVP 的任务列表只用于本地下载操作，不提供服务器视频库、用户归属、分享 token 或容量配额。

## Cookie 管理

桌面版支持两种 Cookie 使用方式：

- 手动保存 Netscape Cookie 文本。
- 设置浏览器 Cookie 来源，由 `yt-dlp` 在下载时读取 Edge、Chrome 或 Firefox 的 Cookie。

手动 Cookie 文件优先级更高。如果已经保存了手动 Cookie，下载时会优先使用手动 Cookie；只有没有手动 Cookie 文件时，才会使用浏览器 Cookie 来源。

推荐流程：

1. 优先尝试“浏览器 Cookie 来源”，选择当前已经登录视频网站的浏览器。
2. 如果浏览器来源不可用，再从浏览器扩展导出 Netscape Cookie 文本并粘贴保存。
3. Cookie 失效或需要更换账号时，先点击“删除 Cookie”，再重新保存或重新选择浏览器来源。

注意事项：

- Cookie 只保存在当前 Windows 用户的 GoTube Desktop 本地数据目录。
- Cookie 不会写回项目根目录的 `cookies.txt`。
- Cookie 内容必须是 Netscape 格式，否则会被拒绝。
- 浏览器 Cookie 来源依赖 `yt-dlp` 的浏览器 Cookie 读取能力；如果浏览器正在运行或系统权限限制导致读取失败，需要关闭浏览器后重试，或改用手动 Cookie。

## ffmpeg 与 yt-dlp

桌面版会检测：

- 已配置的 `ffmpeg` 路径。
- 系统 `PATH` 中的 `ffmpeg`。
- 当前 Python 环境中的 `yt-dlp`。

如果 `ffmpeg` 检测失败，可以在设置中填写 `ffmpeg.exe` 的完整路径。`yt-dlp` 可以通过桌面版按钮触发升级，也可以手工执行：

```powershell
python -m pip install -U yt-dlp
```

## 打包 Windows 可执行文件

先安装桌面依赖，然后执行环境诊断：

```powershell
python scripts/desktop_doctor.py
```

该命令会检查 `pywebview`、`yt-dlp`、`pyinstaller`、`ffmpeg` 和 `node` 的可用状态。`ffmpeg` 与 `node` 按辅助项展示；缺失时应按实际用途处理，其中 `ffmpeg` 会影响音视频分离格式合并，`node` 会影响前端脚本语法自检。

如果需要在自动化流程中把关键依赖缺失视为失败，可以执行：

```powershell
python scripts/desktop_doctor.py --strict
```

确认环境后，执行桌面版自检：

```powershell
python scripts/desktop_check.py
```

自检会运行桌面版单元测试、前端脚本语法检查和 Python 编译检查。自检通过后，推荐用固定构建脚本打包：

```powershell
python scripts/desktop_build.py
```

该脚本会先执行 `scripts/desktop_doctor.py --strict`，再执行 `scripts/desktop_check.py`，然后调用 PyInstaller。需要手工排查 PyInstaller 参数时，可以直接执行底层命令：

```powershell
pyinstaller --clean --noconfirm --distpath desktop_dist --workpath desktop_build desktop/packaging/gotube-desktop.spec
```

打包输出目录：

```text
desktop_dist\
```

中间构建目录：

```text
desktop_build\
```

这两个目录已加入 `.gitignore`，不要提交到仓库。

## 当前限制

- 暂不提供自动安装 `ffmpeg`。
- 暂不提供浏览器 Cookie 自动抽取。
- 暂不提供下载队列持久化恢复。
- 暂不提供多用户、分享链接、后台管理和服务器视频库能力。

这些限制是 MVP 选择，不影响 Web 版现有功能。
