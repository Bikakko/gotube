# GoTube Desktop Windows 使用说明

本文面向 GoTube Desktop 当前 Windows MVP。桌面版只保留单机下载能力，不接入 Web 端的多用户视频库、邀请码、分享链接和后台管理。

## 运行环境

- Windows 10 或 Windows 11
- Python 3.11 及以上
- 可访问目标视频站点的网络环境
- 建议准备可用的 `ffmpeg`

## 安装依赖

在项目根目录执行：

```powershell
python -m venv .venv-desktop
.\.venv-desktop\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r requirements-desktop.txt
```

`requirements-desktop.txt` 包含：

- `PySide6`：桌面原生界面
- `pyinstaller`：打包 Windows 可执行文件
- `yt-dlp`：视频解析与下载

## 开发模式启动

```powershell
python -m desktop.app
```

首次启动后，桌面版会在当前 Windows 用户目录下创建本地配置。默认保存目录：

```text
%USERPROFILE%\Downloads\GoTube
```

该配置只影响桌面版，不读取也不修改服务端 `.env`。

## 基础使用

1. 打开桌面程序
2. 在“下载”页输入视频链接
3. 点击“开始下载”
4. 下载完成后，可在任务列表中打开文件位置

当前桌面版任务列表仅服务本地下载，不提供视频库归属、分享和多用户能力。

## Cookie 管理

桌面版支持两种 Cookie 方式：

- 手动粘贴 Netscape 格式 Cookie
- 从浏览器导入 Cookie，来源支持 Edge、Chrome、Firefox

使用规则：

- 手动 Cookie 优先级高于浏览器 Cookie
- 更换账号前，建议先点击“删除 Cookie”
- Cookie 仅保存在当前 Windows 用户本地目录，不会写回项目根目录的 `cookies.txt`

推荐流程：

1. 先尝试“浏览器 Cookie”
2. 如果导入失败，再手动保存 Netscape 格式 Cookie
3. 失效后先“删除 Cookie”，再重新导入或保存

## ffmpeg 与 yt-dlp

桌面版会检测：

- 当前 Python 环境内的 `yt-dlp`
- 已配置路径或系统 `PATH` 中的 `ffmpeg`

如果 `ffmpeg` 未找到，可在“设置”页指定 `ffmpeg.exe` 路径。`yt-dlp` 可在“设置”页触发升级，也可以手工执行：

```powershell
python -m pip install -U yt-dlp
```

## 环境诊断

先执行：

```powershell
python scripts/desktop_doctor.py
```

该命令会检查 `PySide6`、`yt-dlp`、`pyinstaller` 和 `ffmpeg`。

如果要在自动化流程里把缺失关键依赖视为失败，执行：

```powershell
python scripts/desktop_doctor.py --strict
```

## 自检与打包

自检：

```powershell
python scripts/desktop_check.py
```

该脚本会运行桌面端单元测试和 Python 编译检查。

打包：

```powershell
python scripts/desktop_build.py
```

该脚本会先执行：

- `scripts/desktop_doctor.py --strict`
- `scripts/desktop_check.py`

然后调用：

```powershell
python -m PyInstaller --clean --noconfirm --distpath desktop_dist --workpath desktop_build desktop/packaging/gotube-desktop.spec
```

打包输出目录：

```text
desktop_dist\
```

中间构建目录：

```text
desktop_build\
```

这两个目录已经加入 `.gitignore`。

## 当前限制

- 暂不自动安装 `ffmpeg`
- 暂不自动抓取浏览器登录态之外的额外认证信息
- 暂不提供下载队列持久化恢复
- 暂不接入多用户、分享和后台管理能力
