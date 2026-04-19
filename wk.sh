#!/usr/bin/env bash
# GoTube 生产环境启动脚本 (v3.0.1)
# 使用 gunicorn + uvicorn workers 模式

set -e

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
VENV_DIR="${GOTUBE_VENV_DIR:-$PROJECT_DIR/venv}"
PIDFILE="$PROJECT_DIR/.server.pid"
LOGFILE="$PROJECT_DIR/server.log"

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

usage() {
    echo -e "${YELLOW}用法:${NC}"
    echo "  $0          启动生产服务器"
    echo "  $0 stop     停止服务器"
    echo "  $0 restart  重启服务器"
    echo "  $0 status   查看服务器状态"
    echo "  $0 update   更新 yt-dlp 到最新版本"
    exit 1
}

is_running() {
    if [ -f "$PIDFILE" ]; then
        local pid=$(cat "$PIDFILE")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        else
            rm -f "$PIDFILE"
            return 1
        fi
    fi
    return 1
}

# 获取端口
get_port() {
    if [ -n "${GOTUBE_PORT:-}" ]; then
        echo "$GOTUBE_PORT"
        return 0
    fi

    if [ -f "$PROJECT_DIR/.env" ]; then
        local port
        port=$(awk -F= '
            /^[[:space:]]*GOTUBE_PORT[[:space:]]*=/ {
                value=$2
                gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
                gsub(/^["'\'']|["'\'']$/, "", value)
                print value
                exit
            }
        ' "$PROJECT_DIR/.env")
        if [ -n "$port" ]; then
            echo "$port"
            return 0
        fi
    fi

    echo "8000"
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

# 获取 worker 数量
# 注意：由于下载队列和 WebSocket 进度推送依赖进程内存状态，
# 多 Worker 会导致状态隔离（任务丢失、进度无法推送）。
# 因此固定为 1 个 Worker，使用 asyncio 并发处理请求已足够。
get_workers() {
    echo "1"
}

build_frontend() {
    echo -e "${GREEN}正在混淆前端代码 (www -> www_dist)...${NC}"
    if [ ! -d "$PROJECT_DIR/node_modules" ]; then
        echo -e "${YELLOW}首次运行，正在安装混淆工具依赖...${NC}"
        (cd "$PROJECT_DIR" && npm install --silent)
    fi
    (cd "$PROJECT_DIR" && node build.js)
    if [ $? -ne 0 ]; then
        echo -e "${RED}✗ 前端混淆失败，请检查构建日志${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ 混淆完成，离线 Map 已存至 www_maps${NC}"
}

start() {
    local PORT
    PORT=$(get_port)
    local WORKERS
    WORKERS=$(get_workers)

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
    if [ -f "$PIDFILE" ]; then
        rm -f "$PIDFILE"
    fi

    # 执行前端混淆
    build_frontend

    echo -e "${GREEN}正在启动 GoTube 生产服务器 (v2.3.1)...${NC}"
    echo -e "  端口:    ${YELLOW}$PORT${NC}"
    echo -e "  Workers: ${YELLOW}$WORKERS${NC}"

    # 激活虚拟环境并启动
    if [ ! -f "$VENV_DIR/bin/activate" ]; then
        echo -e "${RED}✗ 未找到虚拟环境: $VENV_DIR${NC}"
        echo -e "${YELLOW}请先在项目目录执行: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt${NC}"
        exit 1
    fi

    source "$VENV_DIR/bin/activate"
    cd "$PROJECT_DIR"

    # 如果配置了 GOTUBE_AUTO_UPDATE_YTDLP=1，则启动时自动更新 yt-dlp
    if grep -q "GOTUBE_AUTO_UPDATE_YTDLP=1" "$PROJECT_DIR/.env" 2>/dev/null; then
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
        --bind "0.0.0.0:$PORT" \
        --pid "$PIDFILE" \
        --access-logfile "$LOGFILE" \
        --error-logfile "$LOGFILE" \
        --daemon

    # 等待服务启动
    sleep 2

    if [ -f "$PIDFILE" ]; then
        local pid=$(cat "$PIDFILE")
        echo -e "${GREEN}✓ 服务器已启动!${NC}"
        echo -e "  PID:      ${YELLOW}$pid${NC}"
        echo -e "  访问地址: ${GREEN}http://localhost:$PORT${NC}"
        echo -e "  日志文件: ${YELLOW}$LOGFILE${NC}"
    else
        echo -e "${RED}✗ 服务器启动失败，请检查日志: $LOGFILE${NC}"
        exit 1
    fi
}

stop() {
    local PORT
    PORT=$(get_port)

    # 如果有 PID 文件，先尝试正常关闭
    if is_running; then
        local pid
        pid=$(cat "$PIDFILE")
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

        rm -f "$PIDFILE"
    fi

    # 如果端口仍被占用，强制清理残留子进程
    if check_port "$PORT"; then
        echo -e "${YELLOW}端口 $PORT 仍被占用，尝试清理残留进程...${NC}"
        force_kill_port "$PORT" || true
    fi

    rm -f "$PIDFILE"
    echo -e "${GREEN}✓ 服务器已停止${NC}"
}

status() {
    local PORT
    PORT=$(get_port)

    if is_running; then
        local pid=$(cat "$PIDFILE")
        echo -e "${GREEN}● 服务器运行中 (v2.3.1)${NC}"
        echo -e "  PID:      $pid"
        echo -e "  访问地址: http://localhost:$PORT"
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
    if [ ! -f "$VENV_DIR/bin/activate" ]; then
        echo -e "${RED}✗ 未找到虚拟环境: $VENV_DIR${NC}"
        exit 1
    fi

    source "$VENV_DIR/bin/activate"
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
