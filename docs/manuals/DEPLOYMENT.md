# GoTube Debian / Linux 最小部署指南 (v4.10.0)

本文指南面向 Debian 12 / 13 及主流 Linux 发行版，说明如何使用 `./wk.sh + .env` 完成服务的首次部署与日常更新。

---

## 一、 前置依赖

首先在服务器安装基础环境依赖：

```bash
sudo apt update
sudo apt install -y git python3 python3-venv ffmpeg nodejs npm
```

---

## 二、 首次部署流程

### 1. 拉取代码

```bash
git clone https://github.com/Bikakko/gotube.git
cd gotube
git checkout master
```

### 2. 初始化环境配置文件

```bash
cp .env.example .env
```

确认 `.env` 中的核心配置（依据实际需求调整）：

```env
GOTUBE_HOST=0.0.0.0
GOTUBE_PORT=8000
GOTUBE_VENV_DIR=./venv
GOTUBE_PID_FILE=./.server.pid
GOTUBE_LOG_FILE=./server.log
GOTUBE_BUILD_FRONTEND=1
GOTUBE_WWW_DIR=www_dist
GOTUBE_DOWNLOAD_DIR=./downloads
GOTUBE_COOKIES_FILE=./data/cookies.txt
GOTUBE_HIDDEN_PATH=7777
GOTUBE_MAX_CONCURRENT=5
GOTUBE_MAX_DOWNLOADS_PER_USER=1
GOTUBE_ADMINS=admin:你的超级安全密码
```

> **注意**：
> - `GOTUBE_ADMINS` 必须修改默认密码。
> - `GOTUBE_HIDDEN_PATH` 仅作为弱隐藏入口，不是生产安全边界；真实安全依赖 HTTPS 及 Token 认证。

### 3. 环境自检与依赖初始化

```bash
./wk.sh doctor   # 启动前自检（检查依赖环境与路径）
./wk.sh init     # 初始化 Python venv，自动安装依赖并编译压缩 www 前端资源
```

### 4. 启动与验证

```bash
./wk.sh restart
./wk.sh status
```

自检访问：`http://服务器IP:8000/health`，若返回 JSON 健康状态说明服务正常运行。

---

## 三、 日常更新流程

代码或依赖更新时：

```bash
cd /你的部署目录/gotube
git pull --ff-only
./wk.sh init
./wk.sh restart
```

> 仅升级下载引擎 (`yt-dlp`)：执行 `./wk.sh update` 即可。

---

## 四、 相关指南

- [systemd 服务托管](SYSTEMD-SERVICE.md)
- [生产环境安全加固说明](SECURITY-HARDENING.md)
