# GoTube Debian / Linux 最小部署指南 (v4.11.0)

本文指南面向 Debian 12 / 13 及主流 Linux 发行版，说明如何使用 `./gotube.sh + .env` 完成服务的首次部署与日常更新。

---

## 一、 前置依赖

最简单的方式是直接运行一键安装脚本（自动处理依赖、配置与初始化，见《操作说明》4.1）：

```bash
curl -fsSL https://raw.githubusercontent.com/Bikakko/gotube/master/scripts/install.sh | bash
```

若偏好手动安装，先装基础环境依赖：

```bash
sudo apt update
sudo apt install -y git python3 python3-venv ffmpeg
# 若已有 Node.js (如 NodeSource 版本) 则跳过下面这行，Debian 的 npm 与 NodeSource nodejs 存在冲突
sudo apt install -y nodejs npm
```

---

## 二、 首次部署流程

### 1. 获取代码

推荐一键安装（目标目录为纯代码，不含 `.git`）：

```bash
curl -fsSL https://raw.githubusercontent.com/Bikakko/gotube/master/scripts/install.sh | bash
```

或手动克隆后执行安装脚本（安装完成后目录内同样不保留 `.git`）：

```bash
git clone https://github.com/Bikakko/gotube.git
cd gotube && ./scripts/install.sh
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
./gotube.sh doctor   # 启动前自检（检查依赖环境与路径）
./gotube.sh init     # 初始化 Python venv，自动安装依赖并编译压缩 www 前端资源
```

### 4. 启动与验证

非 systemd 部署（开发/临时环境）：

```bash
./gotube.sh restart
./gotube.sh status
```

> ⚠ 生产环境建议接入 systemd 托管（见 [systemd 服务托管](SYSTEMD-SERVICE.md)），
> 托管后启停一律 `systemctl start/stop/restart gotube`，不要再手动 `./gotube.sh restart`（会裸起野进程）。

自检访问：`http://服务器IP:8000/health`，若返回 JSON 健康状态说明服务正常运行。

---

## 三、 日常更新流程

代码或依赖更新时（systemd 托管环境会自动走 `systemctl restart`）。升级一律走 `./gotube.sh upgrade`（从远端同步纯代码，生产目录不保留 `.git`），不要在生产目录里手动 `git pull`：

```bash
cd /你的部署目录/gotube
./gotube.sh upgrade
```

> 仅升级下载引擎 (`yt-dlp`)：执行 `./gotube.sh update` 即可。

---

## 四、 相关指南

- [systemd 服务托管](SYSTEMD-SERVICE.md)
- [生产环境安全加固说明](SECURITY-HARDENING.md)
