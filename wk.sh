#!/usr/bin/env bash
# GoTube 生产环境启动脚本 (v4.4.1)
# 使用 gunicorn + uvicorn workers 模式

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

start() {
    runtime_load_common_config
    local PORT="$GOTUBE_PORT"
    local WORKERS="$GOTUBE_WORKERS"
    local ACCESS_LOG_FORMAT='time="%(t)s" remote="%(h)s" method="%(m)s" path="%(U)s" query="%(q)s" status=%(s)s bytes=%(B)s referer="%(f)s" agent="%(a)s"'

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

    echo -e "${GREEN}正在启动 GoTube 生产服务器 (v4.4.1)...${NC}"
    runtime_print_summary
    echo -e "  端口:    ${YELLOW}$PORT${NC}"
    echo -e "  Workers: ${YELLOW}$WORKERS${NC}"

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

    # 使用 gunicorn + uvicorn workers 启动
    gunicorn server.main:app \
        --workers "$WORKERS" \
        --worker-class uvicorn.workers.UvicornWorker \
        --bind "$GOTUBE_HOST:$PORT" \
        --pid "$GOTUBE_PID_FILE" \
        --access-logfile "$GOTUBE_LOG_FILE" \
        --access-logformat "$ACCESS_LOG_FORMAT" \
        --error-logfile "$GOTUBE_LOG_FILE" \
        --capture-output \
        --daemon

    # 等待服务启动
    sleep 2

    if [ -f "$GOTUBE_PID_FILE" ]; then
        local pid=$(cat "$GOTUBE_PID_FILE")
        echo -e "${GREEN}✓ 服务器已启动!${NC}"
        echo -e "  PID:      ${YELLOW}$pid${NC}"
        echo -e "  访问地址: ${GREEN}http://$GOTUBE_HOST:$PORT${NC}"
        echo -e "  日志文件: ${YELLOW}$GOTUBE_LOG_FILE${NC}"
    else
        echo -e "${RED}✗ 服务器启动失败，请检查日志: $GOTUBE_LOG_FILE${NC}"
        exit 1
    fi
}

stop() {
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

    if is_running; then
        local pid=$(cat "$GOTUBE_PID_FILE")
        echo -e "${GREEN}● 服务器运行中 (v4.4.1)${NC}"
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
    *)
        usage
        ;;
esac
