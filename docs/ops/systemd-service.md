# GoTube `systemd` 部署说明

本文基于当前仓库的 `wk.sh + .env` 启动方式，目标是把 GoTube 接入 Debian 12 / 13 的 `systemd`，实现以下能力：

- 开机自启；
- 统一服务管理；
- `journalctl` 日志查看；
- 异常退出后自动拉起。

如果你还没有完成基础部署，先看 [GoTube Debian 服务器最小部署步骤](./debian-minimal-deployment.md)。

## 1. 设计原则

当前推荐做法不是让 `systemd` 直接调用 `gunicorn`，而是继续通过仓库里的 `wk.sh` 来启动和停止服务。

原因：

- `wk.sh` 已经收口了 `.env` 读取、`venv` 初始化、依赖安装、PID 管理和端口清理逻辑；
- 生产启动行为继续保持单一入口；
- 以后启动逻辑有变更时，只要维护 `wk.sh`，不需要同时改 shell 和 service 文件。

因此 service 文件只负责：

- 指定工作目录；
- 调用 `wk.sh start` / `wk.sh stop`；
- 交给 `systemd` 做自动拉起和开机自启。

## 2. 首次接入

### 2.1 准备项目

先按最小部署文档完成以下动作：

```bash
cp .env.example .env
./wk.sh doctor
./wk.sh init
```

### 2.2 复制 service 模板

仓库内模板位置：

- [gotube.service.example](../../deploy/gotube.service.example)

复制到系统目录：

```bash
sudo cp deploy/gotube.service.example /etc/systemd/system/gotube.service
```

### 2.3 修改 service 文件

至少改这两项：

```ini
WorkingDirectory=/你的部署目录/gotube
User=你的运行用户
Group=你的运行用户组
```

如果你就是用 root 部署，也建议后续切到独立服务用户。当前文档先不展开用户隔离。

### 2.4 重新加载 `systemd`

```bash
sudo systemctl daemon-reload
```

### 2.5 启动并设置开机自启

```bash
sudo systemctl enable --now gotube
```

查看状态：

```bash
sudo systemctl status gotube
```

## 3. 日常操作

### 3.1 查看服务状态

```bash
sudo systemctl status gotube
```

### 3.2 启动、停止、重启

```bash
sudo systemctl start gotube
sudo systemctl stop gotube
sudo systemctl restart gotube
```

### 3.3 查看日志

`wk.sh` 本身会写 `server.log`，同时 `systemd` 也能记录标准输出和错误输出。

常用命令：

```bash
sudo journalctl -u gotube -n 100 --no-pager
sudo journalctl -u gotube -f
```

如果你要看应用日志文件：

```bash
tail -f /你的部署目录/gotube/server.log
```

## 4. 推荐更新流程

使用 `systemd` 后，更新也不要绕过 `wk.sh`。

推荐流程：

```bash
cd /你的部署目录/gotube
git pull origin master
./wk.sh init
sudo systemctl restart gotube
```

这样依赖补齐和服务重启仍然由现有脚本负责。

## 5. 故障排查

### 5.1 `systemctl start gotube` 失败

先看：

```bash
sudo systemctl status gotube
sudo journalctl -u gotube -n 100 --no-pager
```

再看仓库内自检结果：

```bash
cd /你的部署目录/gotube
./wk.sh doctor
```

通常问题会落在：

- `WorkingDirectory` 填错；
- `User` 没有项目目录权限；
- `.env` 配置缺失；
- `venv` 尚未初始化；
- `ffmpeg` 或 Python 依赖缺失。

### 5.2 服务看起来启动了，但页面打不开

优先检查：

```bash
cat .env | grep GOTUBE_PORT
cat .env | grep GOTUBE_HOST
sudo ss -tlnp | grep 8000
```

确认服务到底监听在哪个地址和端口。

### 5.3 改了 `.env` 没生效

`.env` 变更后，需要重启服务：

```bash
sudo systemctl restart gotube
```

## 6. 当前建议的边界

当前阶段建议：

- 用 `systemd` 做进程守护；
- 用 `wk.sh` 做应用启动；
- 用 `.env` 做应用配置；
- 用 `journalctl + server.log` 做问题排查。

不要在 `systemd` 里复制一套 GoTube 业务配置，也不要再单独写一套 `gunicorn` 启动参数，否则又会回到多入口维护。
