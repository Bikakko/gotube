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

桌面版支持手动保存 Netscape Cookie 文本。推荐从浏览器扩展导出 Cookie 后粘贴到桌面版设置区域。

注意事项：

- Cookie 只保存在当前 Windows 用户的 GoTube Desktop 本地数据目录。
- Cookie 不会写回项目根目录的 `cookies.txt`。
- Cookie 内容必须是 Netscape 格式，否则会被拒绝。
- 浏览器 Cookie 导入目前是占位能力，后续版本再接入实际导入流程。

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

先安装桌面依赖，然后执行：

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
