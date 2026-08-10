# GoTube systemd 服务托管指南 (v4.10.0)

本文指南说明如何将 GoTube 接入 Linux (`systemd`) 实现开机自启、后台守护与日志托管。

---

## 一、 设计原则

`systemd` 仅负责：
- 开机服务自启
- 进程挂掉后自动拉起恢复
- 使用 `journalctl` 统一下发日志查阅

而 Python 虚拟环境、依赖初始化及前端编译构建依然由 `./gotube.sh` 脚本统一掌控。

---

## 二、 配置步骤

### 1. 拷贝服务配置文件

将模板复制到系统 `systemd` 目录：

```bash
sudo cp deploy/gotube.service.example /etc/systemd/system/gotube.service
```

### 2. 编辑配置文件

编辑 `/etc/systemd/system/gotube.service`，确认或调整路径与用户组：

```ini
[Unit]
Description=GoTube Video Downloader & Library Service
After=network.target

[Service]
Type=forking
WorkingDirectory=/你的实际部署目录/gotube
ExecStart=/你的实际部署目录/gotube/gotube.sh start
ExecStop=/你的实际部署目录/gotube/gotube.sh stop
ExecReload=/你的实际部署目录/gotube/gotube.sh restart
PIDFile=/你的实际部署目录/gotube/.server.pid
User=运行用户
Group=运行用户组
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

### 3. 重载并开启开机自启

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now gotube
```

---

## 三、 日常管理命令

```bash
sudo systemctl start gotube      # 启动服务
sudo systemctl stop gotube       # 停止服务
sudo systemctl restart gotube    # 重启服务
sudo systemctl status gotube     # 查看服务运行状态
sudo journalctl -u gotube -f     # 实时查看控制台输出日志
```

---

## 四、 更新流程

```bash
cd /你的部署目录/gotube
git pull --ff-only
./gotube.sh init
sudo systemctl restart gotube
```
