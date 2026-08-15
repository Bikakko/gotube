#!/usr/bin/env bash
# GoTube 生产环境启动脚本
# 使用 uvicorn 直接运行（单进程，systemd 负责保活）

set -e

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# shellcheck disable=SC1091
source "$PROJECT_DIR/scripts/gotube_runtime.sh"
runtime_load_common_config

usage() {
    echo -e "${YELLOW}用法:${NC}"
    echo "  $0          启动生产服务器"
    echo "  $0 init     初始化虚拟环境、依赖和前端构建"
    echo "  $0 doctor   检查当前启动环境"
    echo "  $0 stop     停止服务器"
    echo "  $0 restart  重启服务器"
    echo "  $0 status   查看服务器状态"
    echo "  $0 update   更新 yt-dlp 到最新版本"
    echo "  $0 upgrade  一键升级 (备份数据库 → 同步代码 → 更新依赖 → 重建前端 → 自动重启)"
    echo ""
    echo "  ⚠ 生产环境(systemd 托管)启停一律 systemctl start/stop/restart gotube，"
    echo "    本脚本的 start/stop/restart 仅限非 systemd 部署；upgrade/doctor/status 不受限。"
    exit 1
}

is_running() {
    if [ -f "$GOTUBE_PID_FILE" ]; then
        local pid=$(cat "$GOTUBE_PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        else
            rm -f "$GOTUBE_PID_FILE"
            return 1
        fi
    fi
    return 1
}

# 检查端口是否被占用
check_port() {
    local port=$1
    if command -v lsof &>/dev/null; then
        lsof -i ":$port" -t &>/dev/null
        return $?
    elif command -v ss &>/dev/null; then
        ss -tlnp | grep -q ":$port "
        return $?
    elif command -v netstat &>/dev/null; then
        netstat -tlnp 2>/dev/null | grep -q ":$port "
        return $?
    fi
    return 1
}

# 获取占用端口的所有 PID
get_port_pids() {
    local port=$1
    if command -v lsof &>/dev/null; then
        lsof -ti ":$port" 2>/dev/null
    elif command -v ss &>/dev/null; then
        ss -tlnp | grep ":$port " | grep -oP 'pid=\K[0-9]+'
    elif command -v netstat &>/dev/null; then
        netstat -tlnp 2>/dev/null | grep ":$port " | grep -oP '[0-9]+/' | grep -oP '^[0-9]+'
    fi
}

# 强制清理占用端口的所有进程
force_kill_port() {
    local port=$1
    local pids
    pids=$(get_port_pids "$port")
    if [ -n "$pids" ]; then
        echo -e "${YELLOW}发现进程占用端口 $port，正在强制终止...${NC}"
        echo "$pids" | while read -r pid; do
            if [ -n "$pid" ]; then
                echo -e "  终止 PID: $pid"
                kill -9 "$pid" 2>/dev/null || true
            fi
        done
        sleep 1
        # 验证是否已清理
        if check_port "$port"; then
            echo -e "${RED}✗ 端口 $port 仍被占用，请手动处理${NC}"
            return 1
        fi
        echo -e "${GREEN}✓ 端口 $port 已释放${NC}"
        return 0
    fi
    return 1
}

# 检测当前是否由 systemd 托管（系统或用户级 gotube.service active）。
# 生产约定：systemd 托管下启停一律走 systemctl，手动跑本脚本的
# start/stop 会 kill 掉 systemd 进程并裸起野进程，造成孤儿进程事故。
systemd_managed() {
    [ "${GOTUBE_ALLOW_SYSTEMD_OVERRIDE:-0}" = "1" ] && return 1
    command -v systemctl &>/dev/null || return 1
    systemctl is-active --quiet gotube 2>/dev/null && return 0
    systemctl --user is-active --quiet gotube 2>/dev/null
}

# 返回当前托管 gotube 的 systemctl 命令前缀（用户级服务优先，其次系统级）
systemctl_cmd() {
    if systemctl --user list-unit-files gotube.service 2>/dev/null | grep -q '^gotube\.service'; then
        echo "systemctl --user"
    else
        echo "systemctl"
    fi
}

systemd_guard() {
    if systemd_managed; then
        echo -e "${RED}✗ 检测到 gotube 服务正由 systemd 托管${NC}"
        echo -e "${YELLOW}生产环境启停请改用: $(systemctl_cmd) ${1:-restart} gotube${NC}"
        echo -e "  手动 ./gotube.sh ${2:-start} 会杀掉 systemd 进程并裸起野进程（曾导致 502 事故）"
        echo -e "  确需绕过时: GOTUBE_ALLOW_SYSTEMD_OVERRIDE=1 $0 ${2:-start}"
        exit 1
    fi
}

start() {
    systemd_guard restart start
    runtime_load_common_config
    local PORT="$GOTUBE_PORT"

    # 端口预检
    if check_port "$PORT"; then
        echo -e "${YELLOW}⚠ 端口 $PORT 已被占用${NC}"
        if force_kill_port "$PORT"; then
            echo -e "${GREEN}✓ 端口已释放，继续启动...${NC}"
        else
            echo -e "${RED}✗ 无法释放端口 $PORT，请手动处理后重试${NC}"
            echo -e "${YELLOW}提示: lsof -i :$PORT 或 fuser -k $PORT/tcp${NC}"
            exit 1
        fi
    fi

    # 清理可能的残留 PID 文件
    if [ -f "$GOTUBE_PID_FILE" ]; then
        rm -f "$GOTUBE_PID_FILE"
    fi

    runtime_ensure_venv || exit 1
    runtime_ensure_python_deps prod || exit 1
    runtime_build_frontend || exit 1

    echo -e "${GREEN}正在启动 GoTube 生产服务器...${NC}"
    runtime_print_summary
    echo -e "  端口:    ${YELLOW}$PORT${NC}"

    runtime_activate_venv || exit 1
    cd "$PROJECT_DIR"

    # 如果配置了 GOTUBE_AUTO_UPDATE_YTDLP=1，则启动时自动更新 yt-dlp
    if [ "$GOTUBE_AUTO_UPDATE_YTDLP" = "1" ]; then
        update_ytdlp
        echo ""
    fi

    # 清除可能冲突的系统环境变量，确保使用 .env 文件配置
    unset GOTUBE_PORT GOTUBE_HIDDEN_PATH GOTUBE_MAX_CONCURRENT
    unset GOTUBE_DOWNLOAD_DIR GOTUBE_COOKIES_FILE GOTUBE_WARP_PROXY
    unset GOTUBE_DEBUG GOTUBE_ADMINS GOTUBE_LOG_LEVEL GOTUBE_DB_FILE

    # 使用 uvicorn 直接启动
    nohup python -m uvicorn server.main:app \
        --host "$GOTUBE_HOST" \
        --port "$PORT" \
        >> "$GOTUBE_LOG_FILE" 2>&1 &
    echo $! > "$GOTUBE_PID_FILE"

    # 等待服务启动
    sleep 2

    if [ -f "$GOTUBE_PID_FILE" ] && kill -0 "$(cat "$GOTUBE_PID_FILE")" 2>/dev/null; then
        local pid=$(cat "$GOTUBE_PID_FILE")
        echo -e "${GREEN}✓ 服务器已启动!${NC}"
        echo -e "  PID:      ${YELLOW}$pid${NC}"
        echo -e "  访问地址: ${GREEN}http://$GOTUBE_HOST:$PORT${NC}"
        echo -e "  日志文件: ${YELLOW}$GOTUBE_LOG_FILE${NC}"
    else
        echo -e "${RED}✗ 服务器启动失败，请检查日志: $GOTUBE_LOG_FILE${NC}"
        rm -f "$GOTUBE_PID_FILE"
        exit 1
    fi
}

stop() {
    systemd_guard stop stop
    runtime_load_common_config
    local PORT="$GOTUBE_PORT"

    # 如果有 PID 文件，先尝试正常关闭
    if is_running; then
        local pid
        pid=$(cat "$GOTUBE_PID_FILE")
        echo -e "${YELLOW}正在停止服务器 (PID: $pid)...${NC}"

        # 发送 SIGTERM，给进程优雅退出的机会
        kill -TERM "$pid" 2>/dev/null || true

        # 等待最多10秒
        for i in $(seq 1 10); do
            if ! kill -0 "$pid" 2>/dev/null; then
                break
            fi
            sleep 1
        done

        # 如果进程还在，强制杀死
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "${YELLOW}进程未响应，强制终止...${NC}"
            kill -9 "$pid" 2>/dev/null || true
            sleep 1
        fi

        rm -f "$GOTUBE_PID_FILE"
    fi

    # 如果端口仍被占用，强制清理残留子进程
    if check_port "$PORT"; then
        echo -e "${YELLOW}端口 $PORT 仍被占用，尝试清理残留进程...${NC}"
        force_kill_port "$PORT" || true
    fi

    rm -f "$GOTUBE_PID_FILE"
    echo -e "${GREEN}✓ 服务器已停止${NC}"
}

status() {
    runtime_load_common_config
    local PORT="$GOTUBE_PORT"

    # systemd 托管时无 .server.pid 文件，直接按服务状态展示，避免误报残留进程
    if systemd_managed; then
        echo -e "${GREEN}● 服务器运行中（systemd 托管）${NC}"
        echo -e "  访问地址: http://$GOTUBE_HOST:$PORT"
        if [ "$(systemctl_cmd)" = "systemctl" ]; then
            echo -e "  详情/日志: systemctl status gotube / journalctl -u gotube -f"
        else
            echo -e "  详情/日志: systemctl --user status gotube / journalctl --user -u gotube -f"
        fi
        return
    fi

    if is_running; then
        local pid=$(cat "$GOTUBE_PID_FILE")
echo -e "${GREEN}● 服务器运行中${NC}"
        echo -e "  PID:      $pid"
        echo -e "  访问地址: http://$GOTUBE_HOST:$PORT"
    elif check_port "$PORT"; then
        local pids
        pids=$(get_port_pids "$PORT")
        echo -e "${YELLOW}⚠ 端口 $PORT 被占用，但无 PID 记录${NC}"
        echo -e "  占用 PID: ${pids:-未知}"
        echo -e "  ${YELLOW}可能是残留进程，建议执行 $0 stop${NC}"
    else
        echo -e "${RED}○ 服务器未运行${NC}"
    fi
}

update_ytdlp() {
    runtime_load_common_config
    runtime_activate_venv || exit 1
    echo -e "${YELLOW}正在更新 yt-dlp...${NC}"

    # 记录当前版本
    local old_ver
    old_ver=$(yt-dlp --version 2>/dev/null || echo "未知")

    pip install --upgrade yt-dlp >/dev/null 2>&1

    local new_ver
    new_ver=$(yt-dlp --version 2>/dev/null || echo "未知")

    echo -e "${GREEN}✓ yt-dlp 更新完成${NC}"
    echo -e "  旧版本: $old_ver"
    echo -e "  新版本: $new_ver"

    # 如果服务正在运行，提示重启
    if is_running; then
        echo -e "${YELLOW}⚠ 服务正在运行，请执行 $0 restart 使更新生效${NC}"
    fi
}

# 纯代码同步：从远端仓库浅克隆到临时目录，仅同步代码文件到生产目录，
# 生产目录不保留 .git（.env/数据库/downloads 等运行时文件不在仓库内，不受影响）
sync_code_from_remote() {
    local repo_url="${GOTUBE_REPO_URL:-}"
    local branch="${GOTUBE_BRANCH:-}"
    if [ -z "$repo_url" ] && [ -f .env ]; then
        repo_url="$(sed -n 's/^GOTUBE_REPO_URL=//p' .env | tail -n1)"
        branch="${branch:-$(sed -n 's/^GOTUBE_BRANCH=//p' .env | tail -n1)}"
    fi
    repo_url="${repo_url:-https://github.com/Bikakko/gotube.git}"

    command -v git >/dev/null 2>&1 || { echo -e "${RED}✗ 未安装 git，无法同步代码${NC}"; return 1; }

    local tmp_dir
    tmp_dir="$(mktemp -d /tmp/gotube-upgrade.XXXXXX)" || return 1
    echo "  仓库: $repo_url${branch:+ 分支: $branch}"
    if ! git clone --quiet --depth 1 ${branch:+--branch "$branch"} "$repo_url" "$tmp_dir/src"; then
        rm -rf "$tmp_dir"
        echo -e "${RED}✗ 代码克隆失败（网络或仓库地址异常），升级中止${NC}"
        return 1
    fi

    # 覆盖同步全部仓库文件；随后移除 .git，保证生产目录为纯代码
    cp -a "$tmp_dir/src/." "$PROJECT_DIR/"
    rm -rf "$tmp_dir" "$PROJECT_DIR/.git"
    echo -e "${GREEN}✓ 代码同步完成（纯代码部署，不含 .git）${NC}"
    echo -e "  提示: 远端已删除的文件不会自动清理，如需彻底一致可手动比对"
}

# 一键升级：备份 → 同步代码 → 依赖 → 前端 → yt-dlp → 自动重启
upgrade() {
    runtime_load_common_config
    cd "$PROJECT_DIR"

    local old_ver
    old_ver="$(cat VERSION 2>/dev/null || echo '未知')"
    local was_running=0
    is_running && was_running=1

    echo -e "${GREEN}GoTube 升级流程 (当前版本: ${YELLOW}v${old_ver}${GREEN})${NC}"

    # [1/6] 升级前数据库备份
    echo -e "${YELLOW}[1/6] 备份数据库...${NC}"
    if runtime_activate_venv 2>/dev/null && \
        python -c "from server.backup import perform_backup; b = perform_backup(); print('  备份文件:', b if b else '无')" 2>/dev/null; then
        echo -e "${GREEN}✓ 数据库备份完成${NC}"
    else
        echo -e "${YELLOW}⚠ 数据库备份跳过 (虚拟环境或备份模块不可用)${NC}"
    fi

    # [2/6] 同步最新代码（纯代码部署，生产目录不保留 .git）
    echo -e "${YELLOW}[2/6] 同步最新代码...${NC}"
    if [ -d .git ]; then
        diff_rc=0
        git diff --quiet HEAD -- >/dev/null 2>&1 || diff_rc=$?
        if [ "$diff_rc" -eq 1 ]; then
            echo -e "${RED}✗ 检测到本地未提交改动，升级中止${NC}"
            echo -e "${YELLOW}提示: 生产目录不应有本地改动；如需保留请手动备份后 git checkout . 再重试${NC}"
            exit 1
        elif [ "$diff_rc" -gt 1 ]; then
            echo -e "${YELLOW}⚠ 无法检查本地改动 (git 不可用/无权限)，继续同步${NC}"
        fi
        echo "  检测到旧式 git 部署，本次升级后自动转为纯代码部署..."
    fi
    sync_code_from_remote || exit 1

    local new_ver
    new_ver="$(cat VERSION 2>/dev/null || echo '未知')"

    # [3/6] 更新 Python 依赖
    echo -e "${YELLOW}[3/6] 更新 Python 依赖...${NC}"
    runtime_ensure_python_deps prod || exit 1

    # [4/6] 重建前端 (仅当开启 GOTUBE_BUILD_FRONTEND=1)
    echo -e "${YELLOW}[4/6] 检查前端资源...${NC}"
    if [ "$GOTUBE_BUILD_FRONTEND" = "1" ]; then
        runtime_install_node_deps || exit 1
        GOTUBE_BUILD_FRONTEND=1 runtime_build_frontend || exit 1
    else
        echo "  GOTUBE_BUILD_FRONTEND!=1，跳过前端构建"
    fi

    # [5/6] 更新 yt-dlp 至最新版
    echo -e "${YELLOW}[5/6] 更新 yt-dlp...${NC}"
    runtime_activate_venv || exit 1
    if pip install --upgrade yt-dlp >/dev/null 2>&1; then
        echo -e "${GREEN}✓ yt-dlp: $(yt-dlp --version 2>/dev/null || echo '未知')${NC}"
    else
        echo -e "${YELLOW}⚠ yt-dlp 更新失败 (网络异常?)，沿用当前版本继续${NC}"
    fi

    # [6/6] 升级前在运行则自动重启
    echo -e "${YELLOW}[6/6] 完成收尾...${NC}"
    if systemd_managed; then
        local ctl
        ctl="$(systemctl_cmd)"
        echo "  检测到 systemd 托管，使用 ${ctl} 重启..."
        if ${ctl} restart gotube; then
            echo -e "${GREEN}✓ 服务已由 systemd 重启${NC}"
        else
            echo -e "${RED}✗ ${ctl} restart gotube 失败，请检查: ${ctl} status gotube${NC}"
            exit 1
        fi
    elif [ "$was_running" = "1" ]; then
        echo "  检测到服务运行中，自动重启..."
        stop
        sleep 1
        start
    elif command -v systemctl &>/dev/null && { systemctl list-unit-files gotube.service 2>/dev/null | grep -q gotube.service || systemctl --user list-unit-files gotube.service 2>/dev/null | grep -q gotube.service; }; then
        echo -e "${YELLOW}提示: 检测到 gotube.service（当前未运行），执行 $(systemctl_cmd) start gotube 启动${NC}"
    else
        echo -e "${YELLOW}提示: 执行 $0 start 启动服务${NC}"
    fi

    echo -e "${GREEN}✓ 升级完成: v${old_ver} → v${new_ver}${NC}"
}

# 主逻辑
case "${1:-start}" in
    init)
        runtime_init prod
        ;;
    doctor)
        runtime_doctor prod
        ;;
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        sleep 1
        start
        ;;
    status)
        status
        ;;
    update)
        update_ytdlp
        ;;
    upgrade)
        upgrade
        ;;
    *)
        usage
        ;;
esac
