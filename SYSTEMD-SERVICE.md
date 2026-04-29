# GoTube systemd 部署

本文说明如何把当前 `wk.sh + .env` 启动方式接入 Debian 12 / 13 的 `systemd`。

如果你还没有完成基础部署，先看 [Debian 最小部署](DEPLOYMENT.md)。

## 设计原则

`systemd` 只负责：

- 开机自启
- 统一进程管理
- 异常退出后自动拉起
- 通过 `journalctl` 查看服务日志

应用启动、停止、依赖初始化仍统一通过 `wk.sh` 完成，避免维护第二套启动参数。

## 接入步骤

1. 准备项目

```bash
cp .env.example .env
./wk.sh doctor
./wk.sh init
```

2. 复制服务模板

```bash
sudo cp deploy/gotube.service.example /etc/systemd/system/gotube.service
```

3. 修改服务文件

至少调整：

```ini
WorkingDirectory=/你的部署目录/gotube
User=你的运行用户
Group=你的运行用户组
```

4. 重新加载并启用

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now gotube
```

5. 查看状态

```bash
sudo systemctl status gotube
```

## 日常操作

```bash
sudo systemctl start gotube
sudo systemctl stop gotube
sudo systemctl restart gotube
sudo systemctl status gotube
sudo journalctl -u gotube -f
```

## 推荐更新流程

```bash
cd /你的部署目录/gotube
git pull --ff-only
./wk.sh init
sudo systemctl restart gotube
```

## 排障

先看：

```bash
sudo systemctl status gotube
sudo journalctl -u gotube -n 100 --no-pager
./wk.sh doctor
```

常见问题通常集中在：

- `WorkingDirectory` 配置错误
- 运行用户无目录权限
- `.env` 配置不完整
- `venv` 未初始化
- `ffmpeg` 或 Python 依赖缺失
