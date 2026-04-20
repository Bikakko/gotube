# GoTube Debian 服务器最小部署步骤

本文面向 Debian 12 / 13 服务器，目标是用当前仓库内的 `wk.sh + .env` 在 5 分钟内完成首次部署或日常更新。

适用范围：

- 生产或准生产环境；
- 单机部署；
- 直接用 `wk.sh` 管理 Gunicorn 进程；
- 暂不依赖 `systemd`、Nginx、HTTPS。

如果你只是先验证服务是否能启动，按本文执行即可；远程访问、反向代理、证书等后续再补。

## 1. 环境要求

服务器需提前具备以下命令：

- `git`
- `python3`
- `python3-venv`
- `ffmpeg`
- `bash`

Debian 可直接执行：

```bash
sudo apt update
sudo apt install -y git python3 python3-venv ffmpeg
```

## 2. 首次部署

### 2.1 拉取代码

```bash
git clone https://github.com/Bikakko/gotube.git
cd gotube
git checkout master
```

### 2.2 生成配置文件

```bash
cp .env.example .env
```

至少检查这几个配置：

```env
GOTUBE_HOST=0.0.0.0
GOTUBE_PORT=8000
GOTUBE_VENV_DIR=./venv
GOTUBE_PID_FILE=./.server.pid
GOTUBE_LOG_FILE=./server.log
GOTUBE_WORKERS=1
GOTUBE_DOWNLOAD_DIR=./downloads
GOTUBE_HIDDEN_PATH=7777
GOTUBE_ADMINS=admin:请改成你自己的密码
```

说明：

- `GOTUBE_WORKERS` 建议保持 `1`。当前下载队列、WebSocket 状态和内存上下文不适合多 worker 并行。
- `GOTUBE_HOST=0.0.0.0` 表示允许局域网或公网访问；只想本机访问可改为 `127.0.0.1`。
- `GOTUBE_ADMINS` 必须改掉默认值。

### 2.3 执行启动前检查

```bash
./wk.sh doctor
```

作用：

- 检查 Python 是否可用；
- 检查虚拟环境路径；
- 检查 Gunicorn / Uvicorn 依赖；
- 检查当前 `.env` 读取结果；
- 检查日志、PID、端口等关键配置。

如果这里就报错，先修复，再继续。

### 2.4 初始化运行环境

```bash
./wk.sh init
```

作用：

- 自动创建 `venv`；
- 安装 Python 依赖；
- 如果未来启用前端构建开关，会在这里一并处理。

### 2.5 启动服务

```bash
./wk.sh restart
```

查看状态：

```bash
./wk.sh status
```

查看日志：

```bash
tail -f server.log
```

访问健康检查：

```text
http://服务器IP:8000/health
```

如果返回 JSON 状态，说明服务已正常启动。

如果你后续要接入开机自启和进程守护，再看 [GoTube `systemd` 部署说明](D:\工作区\gotube.dev\gotube\docs\ops\systemd-service.md)。

## 3. 日常更新

以后更新代码，不需要重新手工搭环境，直接按下面流程执行：

```bash
cd /你的部署目录/gotube
git pull origin master
./wk.sh init
./wk.sh restart
```

说明：

- `git pull`：拉取最新代码；
- `./wk.sh init`：补齐新增依赖；
- `./wk.sh restart`：重启服务。

这是当前推荐的标准更新流程。

## 4. 最小可用命令集

最常用的只有这几条：

```bash
./wk.sh doctor
./wk.sh init
./wk.sh start
./wk.sh stop
./wk.sh restart
./wk.sh status
./wk.sh update
```

用途说明：

- `doctor`：启动前检查；
- `init`：初始化或补齐依赖；
- `start`：启动服务；
- `stop`：停止服务；
- `restart`：重启服务；
- `status`：查看是否正在运行；
- `update`：仅更新 `yt-dlp`。

## 5. 常见问题

### 5.1 `venv/bin/activate: No such file or directory`

通常是虚拟环境还没创建，或者 `.env` 里的 `GOTUBE_VENV_DIR` 配错了。

先执行：

```bash
./wk.sh init
```

如果仍失败，检查：

```bash
grep GOTUBE_VENV_DIR .env
ls -la venv
```

### 5.2 端口被占用

先看状态：

```bash
./wk.sh status
```

再重启：

```bash
./wk.sh restart
```

`wk.sh` 会优先尝试清理冲突端口和残留 PID。若仍失败，再手工排查：

```bash
lsof -i :8000
```

### 5.3 更新后启动失败

先执行：

```bash
./wk.sh doctor
./wk.sh init
```

再看日志：

```bash
tail -n 100 server.log
```

大多数问题会落在：

- 新依赖未安装；
- `.env` 配置不完整；
- 旧 PID 或端口残留；
- `ffmpeg` 缺失。

## 6. 当前不包含的内容

本文故意不覆盖以下内容：

- Nginx 反向代理；
- HTTPS 证书；
- `systemd` 开机自启；
- 域名配置；
- 负载均衡；
- 容器化部署。

原因很简单：当前目标是先把 GoTube 本体稳定启动起来，其他运维层能力后续单独补文档。
