# GoTube

GoTube 是一个以自部署为前提的多平台视频下载与个人视频库工具，当前主线版本为 `4.10.0`。

## 🚀 快速开始 (Linux 一键安装)

在 Linux / Debian / Ubuntu 服务器终端直接运行以下命令：

```bash
curl -fsSL https://raw.githubusercontent.com/Bikakko/gotube/master/scripts/install.sh | bash
```

*脚本会自动安装系统依赖、克隆代码、生成初始随机密码并完成运行环境初始化。*

## 项目文档指引

- [操作说明](docs/manuals/操作说明.md) — 4.10.0 完整使用与运维指南
- [Debian 最小部署](docs/manuals/DEPLOYMENT.md) — Linux/Debian 生产环境部署说明
- [systemd 部署](docs/manuals/SYSTEMD-SERVICE.md) — systemd 后台服务配置指南
- [安全加固](docs/manuals/SECURITY-HARDENING.md) — 生产环境安全边界与加固说明
- [相册首页说明](docs/manuals/GALLERY-HOME.md) — 相册伪装与首页入口配置
- [Windows 开发环境](docs/manuals/README-Windows.md) — Windows 环境搭建与调试指南

## 关键入口与脚本

- **生产服务启动**：`./wk.sh`（自动检测 Python 虚拟环境、依赖及前端构建）
- **本地开发启动**：`st.bat` (Windows) / `./st.sh` (Linux/macOS)
- **配置模板**：`.env.example`（仅从项目根目录 `.env` 加载）
- **当前版本记录**：`VERSION` (`4.10.0`)

## 安全边界说明

- `GOTUBE_HIDDEN_PATH` 只是下载页和后台入口的弱隐藏路径，不是安全边界。
- 后台与用户数据访问的真实安全边界始终是：HTTPS、Bearer Token、权限校验，以及反向代理层的限流和拦截策略。
- 生产环境不要把“知道隐藏路径”视为授权条件。

## 架构与目录概览

- `server/`：FastAPI 后端应用与业务逻辑（下载队列、视频库管理、认证鉴权、定时备份）
- `www/`：前端源码（全页面统一采用标准 ES Module `type="module"` 架构）
- `www_dist/`：前端生产压缩构建产物（`npm run build` 生成）
- `docs/manuals/`：使用与运维说明文档目录
- `docs/superpowers/`：历史设计计划、规格说明与架构演进文档

## 版本演进与特性

- `4.10.0`
  - **Admin 全面模块化**：admin 后台完成 ES Module 改造，建立规范的 `import`/`export` 依赖体系与事件委托机制。
  - **用户注册门控与自动登录**：下载页支持注册二次密码确认，注册成功自动登录。
  - **邀请码管理增强**：支持邀请码明文显示/复制，并可设置新注册用户的初始视频库存储配额。
  - **用户视频库体验优化**：修复视频库缩略图与播放模态框遮挡问题。
- `4.9.0`
  - **单用户并发控制**：新增 `GOTUBE_MAX_DOWNLOADS_PER_USER` 配置，防止单用户/Session 占满全局下载槽位，下载页支持排队实时显示。
- `4.8.x`
  - **数据库定时备份**：应用内置每日 `VACUUM INTO` 自动备份，保存 3 份冷备。

