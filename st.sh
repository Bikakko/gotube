#!/usr/bin/env bash
# GoTube 启动脚本

set -e

PROJECT_DIR="/root/gotube"
VENV_DIR="$PROJECT_DIR/venv"
PIDFILE="$PROJECT_DIR/.server.pid"

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

usage() {
    echo -e "${YELLOW}用法:${NC}"
    echo "  $0          启动开发服务器（热重载）"
    echo "  $0 stop     停止服务器"
    echo "  $0 restart  重启服务器"
    echo "  $0 status   查看服务器状态"
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
    grep GOTUBE_PORT "$PROJECT_DIR/.env" | cut -d= -f2
}

# 检查端口是否被占用
check_port() {
    local port=$1
    # 尝试使用 lsof
    if command -v lsof &>/dev/null; then
        lsof -i ":$port" -t &>/dev/null
        return $?
    # 备选：使用 ss
    elif command -v ss &>/dev/null; then
        ss -tlnp | grep -q ":$port "
        return $?
    # 备选：使用 netstat
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
    local killed=0
    
    # 循环清理，最多尝试5次
    for attempt in 1 2 3 4 5; do
        pids=$(get_port_pids "$port")
        
        if [ -z "$pids" ]; then
            # 端口已释放
            if [ $killed -gt 0 ]; then
                echo -e "${GREEN}✓ 端口 $port 已释放（已清理 $killed 个进程）${NC}"
            fi
            return 0
        fi
        
        # 清理所有占用端口的进程
        echo -e "${YELLOW}发现进程占用端口 $port，正在强制终止...${NC}"
        echo "$pids" | while read -r pid; do
            if [ -n "$pid" ]; then
                echo -e "  终止 PID: $pid"
                kill -9 "$pid" 2>/dev/null || true
                killed=$((killed + 1))
            fi
        done
        
        sleep 0.5
    done
    
    # 5次尝试后再次检查
    if check_port "$port"; then
        echo -e "${RED}✗ 端口 $port 仍被占用，请手动处理${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✓ 端口 $port 已释放${NC}"
    return 0
}

start() {
    local PORT
    PORT=$(get_port)

    # 端口预检
    if check_port "$PORT"; then
        echo -e "${YELLOW}⚠ 端口 $PORT 已被占用${NC}"
        echo -e "${YELLOW}可能原因: 服务器实例未正确关闭${NC}"

        # 尝试自动清理
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

    echo -e "${GREEN}正在启动 GoTube 开发服务器...${NC}"

    # 激活虚拟环境并启动
    source "$VENV_DIR/bin/activate"
    cd "$PROJECT_DIR"

    # 后台启动 uvicorn
    uvicorn server.main:app --host 0.0.0.0 --port "$PORT" --reload &
    local pid=$!
    echo "$pid" > "$PIDFILE"

    # 注册信号陷阱，确保 Ctrl+C 时优雅退出
    trap 'echo -e "\n${YELLOW}收到退出信号，正在关闭服务器...${NC}"; kill -TERM "$pid" 2>/dev/null; wait "$pid" 2>/dev/null; rm -f "$PIDFILE"; echo -e "${GREEN}✓ 服务器已停止${NC}"; exit 0' SIGINT SIGTERM EXIT

    # 等待服务启动
    sleep 2

    if kill -0 "$pid" 2>/dev/null; then
        echo -e "${GREEN}✓ 服务器已启动!${NC}"
        echo -e "  PID:      ${YELLOW}$pid${NC}"
        echo -e "  访问地址: ${GREEN}http://localhost:$PORT${NC}"
        echo -e "  API文档:  ${GREEN}http://localhost:$PORT/docs${NC}"
        echo -e "${YELLOW}按 Ctrl+C 停止服务器${NC}"
        wait "$pid"
    else
        echo -e "${RED}✗ 服务器启动失败，请检查日志${NC}"
        rm -f "$PIDFILE"
        exit 1
    fi
}

stop() {
    # 首先检查端口占用情况
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

    # 如果端口仍被占用，强制清理所有残留子进程（包括 reloader 和 worker）
    if check_port "$PORT"; then
        echo -e "${YELLOW}端口 $PORT 仍被占用，清理所有残留进程...${NC}"
        force_kill_port "$PORT" || true
    fi

    # 清理 PID 文件
    rm -f "$PIDFILE"
    echo -e "${GREEN}✓ 服务器已停止${NC}"
}

status() {
    local PORT
    PORT=$(get_port)

    if is_running; then
        local pid=$(cat "$PIDFILE")
        echo -e "${GREEN}● 服务器运行中${NC}"
        echo -e "  PID:      $pid"
        echo -e "  访问地址: http://localhost:$PORT"
        echo -e "  API文档:  http://localhost:$PORT/docs"
    elif check_port "$PORT"; then
        # PID 文件不存在但端口被占用
        local pids
        pids=$(get_port_pids "$PORT")
        echo -e "${YELLOW}⚠ 端口 $PORT 被占用，但无 PID 记录${NC}"
        echo -e "  占用 PID: ${pids:-未知}"
        echo -e "  ${YELLOW}可能是残留进程，建议执行 $0 stop${NC}"
    else
        echo -e "${RED}○ 服务器未运行${NC}"
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
    *)
        usage
        ;;
esac
