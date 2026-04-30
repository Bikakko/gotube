# GoTube

GoTube 是一个以自部署为前提的视频下载与个人视频库工具，当前主线版本为 `4.5.0`。

## 根目录文档

- [操作说明](操作说明.md)
- [Debian 最小部署](DEPLOYMENT.md)
- [systemd 部署](SYSTEMD-SERVICE.md)
- [安全加固](SECURITY-HARDENING.md)
- [相册首页说明](GALLERY-HOME.md)
- [Windows 开发环境](README-Windows.md)

## 关键入口

- 服务启动脚本：`wk.sh`
- 本地开发启动：`st.sh` / `st.bat`
- 配置模板：`.env.example`
- 当前版本：`VERSION`

## 安全边界说明

- `GOTUBE_HIDDEN_PATH` 只是下载页和后台入口的弱隐藏路径，不是安全边界。
- 后台与用户数据访问的真实安全边界始终是：HTTPS、Bearer Token、权限校验，以及反向代理层的限流和拦截策略。
- 生产环境不要把“知道隐藏路径”视为授权条件。

## 目录概览

- `server/`：后端应用与业务逻辑
- `www/`：前端静态资源
- `tests/`：自动化测试
- `docs/superpowers/`：计划、设计、工作日志与验收记录

## 运维说明

运维相关文档已提升到根目录，便于部署和排障时直接查阅。`docs/superpowers/` 只保留研发过程文档，不再承担运维入口职责。
