#!/usr/bin/env bash
set -e

# GoTube 一键部署与安装脚本 (Linux / Debian / Ubuntu)

echo "========================================="
echo "      GoTube v4.10.0 一键安装脚本        "
echo "========================================="

# 1. 检查并安装依赖
echo "[1/4] 检查并安装系统依赖 (git, python3, ffmpeg, nodejs)..."
if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq git python3 python3-venv ffmpeg nodejs npm
elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y git python3 ffmpeg nodejs npm
elif command -v yum >/dev/null 2>&1; then
    sudo yum install -y git python3 ffmpeg nodejs npm
fi

# 2. 检查项目目录
if [ -f "wk.sh" ] && [ -d "server" ]; then
    echo "[2/4] 当前已在 GoTube 代码目录内部，跳过克隆步骤。"
else
    INSTALL_DIR="gotube"
    if [ ! -d "$INSTALL_DIR" ]; then
        echo "[2/4] 克隆 GoTube 代码库..."
        git clone https://github.com/Bikakko/gotube.git "$INSTALL_DIR"
        cd "$INSTALL_DIR"
    else
        echo "[2/4] 检测到子目录 $INSTALL_DIR，自动进入并拉取更新..."
        cd "$INSTALL_DIR"
        git pull --ff-only
    fi
fi

# 3. 配置生成
if [ ! -f .env ]; then
    echo "[3/4] 首次运行，生成初始配置 (.env)..."
    cp .env.example .env
    # 随机生成初始管理员密码
    RAND_PASS=$(LC_ALL=C tr -dc A-Za-z0-9 </dev/urandom | head -c 12 2>/dev/null || echo "admin123456")
    if command -v sed >/dev/null 2>&1; then
        sed -i "s/GOTUBE_ADMINS=admin:changeme/GOTUBE_ADMINS=admin:${RAND_PASS}/g" .env
    fi
    echo "-----------------------------------------"
    echo ">> 默认隐藏路径: /7777"
    echo ">> 初始管理员账号: admin"
    echo ">> 初始随机密码: ${RAND_PASS}"
    echo ">> (提示: 可随时在 .env 文件中修改密码)"
    echo "-----------------------------------------"
fi

# 4. 初始化运行环境
echo "[4/4] 初始化 Python 虚拟环境与编译前端..."
./wk.sh init

echo "========================================="
echo "🎉 GoTube 安装完成！"
echo ""
echo "常用操作命令："
echo "  进项目目录: cd $INSTALL_DIR"
echo "  启动服务  : ./wk.sh start"
echo "  停止服务  : ./wk.sh stop"
echo "  查看状态  : ./wk.sh status"
echo "========================================="
