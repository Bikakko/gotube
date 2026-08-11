# GoTube systemd 服务托管指南 (v4.10.0)

本文指南说明如何将 GoTube 接入 Linux (`systemd`) 实现开机自启、后台守护与日志托管。

---

## 一、 设计原则

`systemd` 仅负责：
- 开机服务自启
- 进程挂掉后自动拉起恢复
- 使用 `journalctl` 统一下发日志查阅

而 Python 虚拟环境、依赖初始化及前端编译构建依然由 `./gotube.sh` 脚本统一掌控。

> ⚠ **生产约定（重要，防孤儿进程事故）**：systemd 托管后，启停一律走
> `systemctl start/stop/restart gotube`，**禁止**手动 `./gotube.sh start/restart`——
> 它会强杀 systemd 托管进程再裸起一个不受管理的野进程（曾因此引发 502 事故）。
> `gotube.sh` 检测到服务 active 时会直接拒绝启停；`upgrade`/`doctor`/`status` 不受限。

---

## 二、 配置步骤

### 1. 拷贝服务配置文件

将模板复制到系统 `systemd` 目录：

```bash
sudo cp deploy/gotube.service.example /etc/systemd/system/gotube.service
```

### 2. 编辑配置文件

编辑 `/etc/systemd/system/gotube.service`，把模板中的 `<GOTUBE_DIR>` 占位符
替换为实际部署目录（如 `/root/gotube`，模板不写死任何安装路径）：

```ini
[Unit]
Description=GoTube Service
After=network.target

[Service]
Type=simple
User=运行用户
Group=运行用户组
WorkingDirectory=<GOTUBE_DIR>
ExecStart=<GOTUBE_DIR>/venv/bin/python -m uvicorn server.main:app
Restart=on-failure
RestartSec=5
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
```

要点说明：
- 用项目 `venv` 内的 python 直跑 uvicorn（依赖装在 venv，不用系统 python），
  对应 `Type=simple`；server 自行读取部署目录下的 `.env`，host/port 无需写在 ExecStart。
- 旧版 `Type=forking` + `gotube.sh start` 的写法已废弃，不要从 git 历史/旧文档照搬。

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
./gotube.sh upgrade   # 备份数据库 → 同步纯代码 → 更新依赖 → 重建前端 → 自动 systemctl restart gotube
```

升级的代码同步由脚本从远端仓库完成，生产目录不保留 `.git`，无需也不应手动 `git pull`。
