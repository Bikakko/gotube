#!/usr/bin/env bash
# GoTube 鐢熶骇鐜鍚姩鑴氭湰 (v4.5.1)
# 浣跨敤 gunicorn + uvicorn workers 妯″紡

set -e

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"

# 棰滆壊杈撳嚭
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# shellcheck disable=SC1091
source "$PROJECT_DIR/scripts/gotube_runtime.sh"
runtime_load_common_config

usage() {
    echo -e "${YELLOW}鐢ㄦ硶:${NC}"
    echo "  $0          鍚姩鐢熶骇鏈嶅姟鍣?
    echo "  $0 init     鍒濆鍖栬櫄鎷熺幆澧冦€佷緷璧栧拰鍓嶇鏋勫缓"
    echo "  $0 doctor   妫€鏌ュ綋鍓嶅惎鍔ㄧ幆澧?
    echo "  $0 stop     鍋滄鏈嶅姟鍣?
    echo "  $0 restart  閲嶅惎鏈嶅姟鍣?
    echo "  $0 status   鏌ョ湅鏈嶅姟鍣ㄧ姸鎬?
    echo "  $0 update   鏇存柊 yt-dlp 鍒版渶鏂扮増鏈?
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

# 妫€鏌ョ鍙ｆ槸鍚﹁鍗犵敤
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

# 鑾峰彇鍗犵敤绔彛鐨勬墍鏈?PID
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

# 寮哄埗娓呯悊鍗犵敤绔彛鐨勬墍鏈夎繘绋?
force_kill_port() {
    local port=$1
    local pids
    pids=$(get_port_pids "$port")
    if [ -n "$pids" ]; then
        echo -e "${YELLOW}鍙戠幇杩涚▼鍗犵敤绔彛 $port锛屾鍦ㄥ己鍒剁粓姝?..${NC}"
        echo "$pids" | while read -r pid; do
            if [ -n "$pid" ]; then
                echo -e "  缁堟 PID: $pid"
                kill -9 "$pid" 2>/dev/null || true
            fi
        done
        sleep 1
        # 楠岃瘉鏄惁宸叉竻鐞?
        if check_port "$port"; then
            echo -e "${RED}鉁?绔彛 $port 浠嶈鍗犵敤锛岃鎵嬪姩澶勭悊${NC}"
            return 1
        fi
        echo -e "${GREEN}鉁?绔彛 $port 宸查噴鏀?{NC}"
        return 0
    fi
    return 1
}

start() {
    runtime_load_common_config
    local PORT="$GOTUBE_PORT"
    local WORKERS="$GOTUBE_WORKERS"
    local ACCESS_LOG_FORMAT='time="%(t)s" remote="%(h)s" method="%(m)s" path="%(U)s" query="%(q)s" status=%(s)s bytes=%(B)s referer="%(f)s" agent="%(a)s"'

    # 绔彛棰勬
    if check_port "$PORT"; then
        echo -e "${YELLOW}鈿?绔彛 $PORT 宸茶鍗犵敤${NC}"
        if force_kill_port "$PORT"; then
            echo -e "${GREEN}鉁?绔彛宸查噴鏀撅紝缁х画鍚姩...${NC}"
        else
            echo -e "${RED}鉁?鏃犳硶閲婃斁绔彛 $PORT锛岃鎵嬪姩澶勭悊鍚庨噸璇?{NC}"
            echo -e "${YELLOW}鎻愮ず: lsof -i :$PORT 鎴?fuser -k $PORT/tcp${NC}"
            exit 1
        fi
    fi

    # 娓呯悊鍙兘鐨勬畫鐣?PID 鏂囦欢
    if [ -f "$GOTUBE_PID_FILE" ]; then
        rm -f "$GOTUBE_PID_FILE"
    fi

    runtime_ensure_venv || exit 1
    runtime_ensure_python_deps prod || exit 1
    runtime_build_frontend || exit 1

    echo -e "${GREEN}姝ｅ湪鍚姩 GoTube 鐢熶骇鏈嶅姟鍣?(v4.5.1)...${NC}"
    runtime_print_summary
    echo -e "  绔彛:    ${YELLOW}$PORT${NC}"
    echo -e "  Workers: ${YELLOW}$WORKERS${NC}"

    runtime_activate_venv || exit 1
    cd "$PROJECT_DIR"

    # 濡傛灉閰嶇疆浜?GOTUBE_AUTO_UPDATE_YTDLP=1锛屽垯鍚姩鏃惰嚜鍔ㄦ洿鏂?yt-dlp
    if [ "$GOTUBE_AUTO_UPDATE_YTDLP" = "1" ]; then
        update_ytdlp
        echo ""
    fi

    # 娓呴櫎鍙兘鍐茬獊鐨勭郴缁熺幆澧冨彉閲忥紝纭繚浣跨敤 .env 鏂囦欢閰嶇疆
    unset GOTUBE_PORT GOTUBE_HIDDEN_PATH GOTUBE_MAX_CONCURRENT
    unset GOTUBE_DOWNLOAD_DIR GOTUBE_COOKIES_FILE GOTUBE_WARP_PROXY
    unset GOTUBE_DEBUG GOTUBE_ADMINS GOTUBE_LOG_LEVEL GOTUBE_DB_FILE

    # 浣跨敤 gunicorn + uvicorn workers 鍚姩
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

    # 绛夊緟鏈嶅姟鍚姩
    sleep 2

    if [ -f "$GOTUBE_PID_FILE" ]; then
        local pid=$(cat "$GOTUBE_PID_FILE")
        echo -e "${GREEN}鉁?鏈嶅姟鍣ㄥ凡鍚姩!${NC}"
        echo -e "  PID:      ${YELLOW}$pid${NC}"
        echo -e "  璁块棶鍦板潃: ${GREEN}http://$GOTUBE_HOST:$PORT${NC}"
        echo -e "  鏃ュ織鏂囦欢: ${YELLOW}$GOTUBE_LOG_FILE${NC}"
    else
        echo -e "${RED}鉁?鏈嶅姟鍣ㄥ惎鍔ㄥけ璐ワ紝璇锋鏌ユ棩蹇? $GOTUBE_LOG_FILE${NC}"
        exit 1
    fi
}

stop() {
    runtime_load_common_config
    local PORT="$GOTUBE_PORT"

    # 濡傛灉鏈?PID 鏂囦欢锛屽厛灏濊瘯姝ｅ父鍏抽棴
    if is_running; then
        local pid
        pid=$(cat "$GOTUBE_PID_FILE")
        echo -e "${YELLOW}姝ｅ湪鍋滄鏈嶅姟鍣?(PID: $pid)...${NC}"

        # 鍙戦€?SIGTERM锛岀粰杩涚▼浼橀泤閫€鍑虹殑鏈轰細
        kill -TERM "$pid" 2>/dev/null || true

        # 绛夊緟鏈€澶?0绉?
        for i in $(seq 1 10); do
            if ! kill -0 "$pid" 2>/dev/null; then
                break
            fi
            sleep 1
        done

        # 濡傛灉杩涚▼杩樺湪锛屽己鍒舵潃姝?
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "${YELLOW}杩涚▼鏈搷搴旓紝寮哄埗缁堟...${NC}"
            kill -9 "$pid" 2>/dev/null || true
            sleep 1
        fi

        rm -f "$GOTUBE_PID_FILE"
    fi

    # 濡傛灉绔彛浠嶈鍗犵敤锛屽己鍒舵竻鐞嗘畫鐣欏瓙杩涚▼
    if check_port "$PORT"; then
        echo -e "${YELLOW}绔彛 $PORT 浠嶈鍗犵敤锛屽皾璇曟竻鐞嗘畫鐣欒繘绋?..${NC}"
        force_kill_port "$PORT" || true
    fi

    rm -f "$GOTUBE_PID_FILE"
    echo -e "${GREEN}鉁?鏈嶅姟鍣ㄥ凡鍋滄${NC}"
}

status() {
    runtime_load_common_config
    local PORT="$GOTUBE_PORT"

    if is_running; then
        local pid=$(cat "$GOTUBE_PID_FILE")
        echo -e "${GREEN}鈼?鏈嶅姟鍣ㄨ繍琛屼腑 (v4.5.1)${NC}"
        echo -e "  PID:      $pid"
        echo -e "  璁块棶鍦板潃: http://$GOTUBE_HOST:$PORT"
    elif check_port "$PORT"; then
        local pids
        pids=$(get_port_pids "$PORT")
        echo -e "${YELLOW}鈿?绔彛 $PORT 琚崰鐢紝浣嗘棤 PID 璁板綍${NC}"
        echo -e "  鍗犵敤 PID: ${pids:-鏈煡}"
        echo -e "  ${YELLOW}鍙兘鏄畫鐣欒繘绋嬶紝寤鸿鎵ц $0 stop${NC}"
    else
        echo -e "${RED}鈼?鏈嶅姟鍣ㄦ湭杩愯${NC}"
    fi
}

update_ytdlp() {
    runtime_load_common_config
    runtime_activate_venv || exit 1
    echo -e "${YELLOW}姝ｅ湪鏇存柊 yt-dlp...${NC}"

    # 璁板綍褰撳墠鐗堟湰
    local old_ver
    old_ver=$(yt-dlp --version 2>/dev/null || echo "鏈煡")

    pip install --upgrade yt-dlp >/dev/null 2>&1

    local new_ver
    new_ver=$(yt-dlp --version 2>/dev/null || echo "鏈煡")

    echo -e "${GREEN}鉁?yt-dlp 鏇存柊瀹屾垚${NC}"
    echo -e "  鏃х増鏈? $old_ver"
    echo -e "  鏂扮増鏈? $new_ver"

    # 濡傛灉鏈嶅姟姝ｅ湪杩愯锛屾彁绀洪噸鍚?
    if is_running; then
        echo -e "${YELLOW}鈿?鏈嶅姟姝ｅ湪杩愯锛岃鎵ц $0 restart 浣挎洿鏂扮敓鏁?{NC}"
    fi
}

# 涓婚€昏緫
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
