# GoTube Debian 最小部署

本文面向 Debian 12 / 13，目标是在当前仓库结构下，用 `wk.sh + .env` 完成首次部署和后续更新。

## 前置依赖

安装以下系统命令：

```bash
sudo apt update
sudo apt install -y git python3 python3-venv ffmpeg nodejs npm
```

## 首次部署

1. 拉取代码

```bash
git clone https://github.com/Bikakko/gotube.git
cd gotube
git checkout master
```

2. 生成配置

```bash
cp .env.example .env
```

至少确认这些配置：

```env
GOTUBE_HOST=0.0.0.0
GOTUBE_PORT=8000
GOTUBE_VENV_DIR=./venv
GOTUBE_PID_FILE=./.server.pid
GOTUBE_LOG_FILE=./server.log
GOTUBE_WORKERS=1
GOTUBE_BUILD_FRONTEND=1
GOTUBE_WWW_DIR=www_dist
GOTUBE_DOWNLOAD_DIR=./downloads
GOTUBE_HIDDEN_PATH=7777
GOTUBE_ADMINS=admin:请改成你自己的密码
```

说明：

- `GOTUBE_WORKERS` 建议保持 `1`，当前下载队列和会话状态不适合多 worker 并行。
- `GOTUBE_ADMINS` 必须替换默认值。

3. 启动前自检

```bash
./wk.sh doctor
```

4. 初始化运行环境

```bash
./wk.sh init
```

5. 启动服务

```bash
./wk.sh restart
./wk.sh status
```

6. 健康检查

```text
http://服务器IP:8000/health
```

## 日常更新

```bash
cd /你的部署目录/gotube
git pull --ff-only
./wk.sh init
./wk.sh restart
```

## 常用命令

```bash
./wk.sh doctor
./wk.sh init
./wk.sh start
./wk.sh stop
./wk.sh restart
./wk.sh status
./wk.sh update
```

`update` 只更新 `yt-dlp`，不更新 GoTube 代码本体。

## 相关文档

- [systemd 部署](SYSTEMD-SERVICE.md)
- [安全加固](SECURITY-HARDENING.md)
