#!/usr/bin/env bash
set -e

# GoTube 一键安装/更新脚本 (Linux / Debian / Ubuntu)
#
# 公开分发用法（任选其一）：
#   curl -fsSL https://raw.githubusercontent.com/Bikakko/gotube/master/scripts/install.sh | bash
#   git clone https://github.com/Bikakko/gotube.git && cd gotube && ./scripts/install.sh
#
# 可通过环境变量定制：
#   GOTUBE_REPO_URL    仓库地址（默认官方仓库，fork 可覆盖）
#   GOTUBE_BRANCH      克隆后切换的分支（默认远端默认分支）
#   GOTUBE_INSTALL_DIR 安装目录（默认 ./gotube）

# curl 管道执行时 stdin 承载脚本内容（bash 从 fd 0 读取脚本本身）；
# 有控制终端时把终端挂到 fd 3 供交互命令 (sudo 密码等) 使用。
# 切勿 exec </dev/tty —— 那会替换脚本自身输入流导致脚本被截断
if [ ! -t 0 ] && (exec </dev/tty) 2>/dev/null; then
    exec 3</dev/tty
    HAS_TTY_IN=1
fi

GOTUBE_REPO_URL="${GOTUBE_REPO_URL:-https://github.com/Bikakko/gotube.git}"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" 2>/dev/null && pwd 2>/dev/null || echo ".")"
GT_VERSION="$(cat "$SCRIPT_DIR/../VERSION" 2>/dev/null || echo "latest")"

echo "========================================="
echo "      GoTube v${GT_VERSION} 一键安装脚本        "
echo "========================================="

# 1. 检查并安装依赖
echo "[1/5] 检查并安装系统依赖 (git, python3, ffmpeg, nodejs)..."
install_pkgs() {
    if command -v apt-get >/dev/null 2>&1; then
        run_sudo apt-get install -y -qq "$@"
    elif command -v dnf >/dev/null 2>&1; then
        run_sudo dnf install -y "$@"
    elif command -v yum >/dev/null 2>&1; then
        run_sudo yum install -y "$@"
    else
        echo "警告: 未找到受支持的包管理器 (apt-get/dnf/yum)，请手动安装: $*"
        return 1
    fi
}

# sudo 调用包装：管道安装场景下从 fd 3 (终端) 读入，保证密码提示可用
run_sudo() {
    if [ "${HAS_TTY_IN:-0}" = "1" ]; then
        sudo "$@" <&3
    else
        sudo "$@"
    fi
}

if command -v apt-get >/dev/null 2>&1; then
    run_sudo apt-get update -qq || echo "警告: apt-get update 失败，尝试使用现有软件源索引继续..."
fi

# 基础依赖与 ffmpeg 单独安装，避免与 nodejs/npm 的包冲突导致整批失败
install_pkgs git python3 python3-venv ffmpeg || echo "警告: 部分基础依赖安装失败，请检查上方输出"

# 已存在 node/npm (如 NodeSource 版本) 时跳过，Debian 的 npm 包会与 NodeSource nodejs 冲突
if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
    install_pkgs nodejs npm || echo "警告: nodejs/npm 安装失败，如已有 Node 环境可忽略"
else
    echo "  检测到已有 node $(node -v) / npm $(npm -v 2>/dev/null)，跳过安装"
fi

# 2. 获取代码：纯代码部署，目标目录不保留 .git
#    新装：浅克隆到临时目录后同步代码；已有安装：走 gotube.sh upgrade 完整升级链
sync_code_into() {
    # $1 = 目标目录；克隆远端仓库并仅同步代码文件（不含 .git）
    local dest="$1"
    local tmp_dir
    tmp_dir="$(mktemp -d /tmp/gotube-install.XXXXXX)" || return 1
    if ! git clone --quiet --depth 1 ${GOTUBE_BRANCH:+--branch "$GOTUBE_BRANCH"} "$GOTUBE_REPO_URL" "$tmp_dir/src"; then
        rm -rf "$tmp_dir"
        echo "✗ 代码克隆失败（网络或仓库地址异常）"
        return 1
    fi
    mkdir -p "$dest"
    cp -a "$tmp_dir/src/." "$dest/"
    rm -rf "$tmp_dir" "$dest/.git"
}

if [ -f "gotube.sh" ] && [ -d "server" ]; then
    echo "[2/5] 检测到已有安装，执行更新流程（.env 配置将保留，并转为纯代码部署）..."
    ./gotube.sh upgrade
elif [ -f "${GOTUBE_INSTALL_DIR:-gotube}/gotube.sh" ] && [ -d "${GOTUBE_INSTALL_DIR:-gotube}/server" ]; then
    INSTALL_DIR="${GOTUBE_INSTALL_DIR:-gotube}"
    echo "[2/5] 检测到已有目录 $INSTALL_DIR，执行更新流程（.env 配置将保留）..."
    cd "$INSTALL_DIR"
    ./gotube.sh upgrade
else
    INSTALL_DIR="${GOTUBE_INSTALL_DIR:-gotube}"
    NEW_INSTALL=1
    echo "[2/5] 获取 GoTube 代码（纯代码部署，不含 .git）: $GOTUBE_REPO_URL"
    sync_code_into "$INSTALL_DIR" || exit 1
    cd "$INSTALL_DIR"
fi

# 3. 配置生成
if [ ! -f .env ]; then
    echo "[3/5] 首次运行，生成初始配置 (.env)..."
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
echo "[4/5] 初始化 Python 虚拟环境与编译前端..."
./gotube.sh init

# 5. 服务托管：新装默认用户级 systemd 服务（日常 systemctl --user 管理，无需 root）；
#    已有安装保持原托管方式不变，仅在检测到旧式 root 系统服务时打印迁移提示
echo "[5/5] 配置服务托管..."
if [ "${NEW_INSTALL:-0}" = "1" ]; then
    if command -v systemctl &>/dev/null && systemctl --user daemon-reload 2>/dev/null; then
        USER_UNIT_DIR="$HOME/.config/systemd/user"
        mkdir -p "$USER_UNIT_DIR"
        cat > "$USER_UNIT_DIR/gotube.service" <<EOF
# GoTube systemd 用户服务 —— 由 scripts/install.sh 生成，以当前用户运行
[Unit]
Description=GoTube Service (user)
After=network.target

[Service]
Type=simple
WorkingDirectory=$(pwd)
EnvironmentFile=$(pwd)/.env
ExecStart=$(pwd)/venv/bin/python -m uvicorn server.main:app --host \${GOTUBE_HOST} --port \${GOTUBE_PORT}
Restart=on-failure
RestartSec=5
TimeoutStopSec=30

[Install]
WantedBy=default.target
EOF
        # linger 保证开机自启且注销后服务不退出（开启需要一次 sudo）
        if ! loginctl show-user "$(id -un)" 2>/dev/null | grep -q 'Linger=yes'; then
            run_sudo loginctl enable-linger "$(id -un)" || echo "警告: enable-linger 失败，注销后服务会停止；可稍后手动执行: sudo loginctl enable-linger $(id -un)"
        fi
        if systemctl --user daemon-reload && systemctl --user enable --now gotube.service; then
            echo "  ✓ 用户级服务已启动并设为开机自启: systemctl --user status gotube"
        else
            echo "  ✗ 用户服务启动失败，查看日志: journalctl --user -u gotube -n 50；也可手动 ./gotube.sh start"
        fi
    else
        echo "  未检测到可用的 systemd 用户会话，跳过服务安装；可手动 ./gotube.sh start"
    fi
else
    echo "  已有安装：保持现有服务托管方式不变"
    if command -v systemctl &>/dev/null \
        && systemctl list-unit-files gotube.service 2>/dev/null | grep -q gotube.service \
        && ! systemctl --user list-unit-files gotube.service 2>/dev/null | grep -q gotube.service; then
        echo "  提示: 检测到旧式系统级 gotube.service（root 运行）。如需收归当前用户，"
        echo "        参考 deploy/gotube.service.example 中的迁移说明（需一次 sudo）"
    fi
fi

GT_VERSION="$(cat VERSION 2>/dev/null || echo "$GT_VERSION")"
echo "========================================="
echo "🎉 GoTube v${GT_VERSION} 安装完成！"
echo ""
echo "常用操作命令："
echo "  进项目目录: cd ${INSTALL_DIR:-.}"
if [ "${NEW_INSTALL:-0}" = "1" ]; then
    echo "  启动服务  : systemctl --user start gotube"
    echo "  停止服务  : systemctl --user stop gotube"
    echo "  查看状态  : systemctl --user status gotube"
    echo "  查看日志  : journalctl --user -u gotube -f"
else
    echo "  启动服务  : ./gotube.sh start"
    echo "  停止服务  : ./gotube.sh stop"
    echo "  查看状态  : ./gotube.sh status"
fi
echo ""
echo "后续更新（任选其一）："
echo "  ./gotube.sh upgrade                # 备份→拉取→依赖→自动重启"
echo "  重跑本脚本                          # 保留 .env，重新初始化环境"
echo "========================================="
