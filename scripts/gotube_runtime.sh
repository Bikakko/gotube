#!/usr/bin/env bash

if [ -z "${PROJECT_DIR:-}" ]; then
    PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
fi

runtime_read_env_value() {
    local key="$1"
    local env_file="$PROJECT_DIR/.env"

    if [ ! -f "$env_file" ]; then
        return 1
    fi

    awk -F= -v key="$key" '
        $0 ~ "^[[:space:]]*" key "[[:space:]]*=" {
            value=$2
            sub(/^[[:space:]]+/, "", value)
            sub(/[[:space:]]+$/, "", value)
            gsub(/^["'\'']|["'\'']$/, "", value)
            print value
            exit
        }
    ' "$env_file"
}

runtime_get_config() {
    local key="$1"
    local default_value="$2"
    local value=""

    if [ -n "${!key:-}" ]; then
        value="${!key}"
    else
        value="$(runtime_read_env_value "$key" 2>/dev/null || true)"
    fi

    if [ -z "$value" ]; then
        value="$default_value"
    fi

    printf '%s\n' "$value"
}

runtime_resolve_path() {
    local raw_path="$1"

    case "$raw_path" in
        "" )
            printf '%s\n' "$PROJECT_DIR"
            ;;
        /* )
            printf '%s\n' "$raw_path"
            ;;
        [A-Za-z]:* )
            printf '%s\n' "$raw_path"
            ;;
        * )
            printf '%s\n' "$PROJECT_DIR/${raw_path#./}"
            ;;
    esac
}

runtime_load_common_config() {
    GOTUBE_HOST="$(runtime_get_config GOTUBE_HOST "0.0.0.0")"
    GOTUBE_PORT="$(runtime_get_config GOTUBE_PORT "8000")"
    GOTUBE_VENV_DIR="$(runtime_resolve_path "$(runtime_get_config GOTUBE_VENV_DIR "./venv")")"
    GOTUBE_PID_FILE="$(runtime_resolve_path "$(runtime_get_config GOTUBE_PID_FILE "./.server.pid")")"
    GOTUBE_LOG_FILE="$(runtime_resolve_path "$(runtime_get_config GOTUBE_LOG_FILE "./server.log")")"
    GOTUBE_BUILD_FRONTEND="$(runtime_get_config GOTUBE_BUILD_FRONTEND "0")"
    GOTUBE_AUTO_INIT_VENV="$(runtime_get_config GOTUBE_AUTO_INIT_VENV "1")"
    GOTUBE_AUTO_INSTALL_DEPS="$(runtime_get_config GOTUBE_AUTO_INSTALL_DEPS "1")"
    GOTUBE_AUTO_UPDATE_YTDLP="$(runtime_get_config GOTUBE_AUTO_UPDATE_YTDLP "0")"
}

runtime_print_summary() {
    echo -e "  项目目录: ${YELLOW}$PROJECT_DIR${NC}"
    echo -e "  Host:     ${YELLOW}$GOTUBE_HOST${NC}"
    echo -e "  端口:     ${YELLOW}$GOTUBE_PORT${NC}"
    echo -e "  虚拟环境: ${YELLOW}$GOTUBE_VENV_DIR${NC}"
    echo -e "  PID 文件: ${YELLOW}$GOTUBE_PID_FILE${NC}"
    if [ -n "${GOTUBE_LOG_FILE:-}" ]; then
        echo -e "  日志文件: ${YELLOW}$GOTUBE_LOG_FILE${NC}"
    fi
}

runtime_has_python() {
    command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1
}

runtime_python_bin() {
    if command -v python3 >/dev/null 2>&1; then
        printf '%s\n' "python3"
    else
        printf '%s\n' "python"
    fi
}

runtime_ensure_venv() {
    if [ -f "$GOTUBE_VENV_DIR/bin/activate" ]; then
        return 0
    fi

    if [ "$GOTUBE_AUTO_INIT_VENV" != "1" ]; then
        echo -e "${RED}✗ 未找到虚拟环境: $GOTUBE_VENV_DIR${NC}"
        echo -e "${YELLOW}请先执行: $0 init${NC}"
        return 1
    fi

    if ! runtime_has_python; then
        echo -e "${RED}✗ 未找到 python3/python，无法自动创建虚拟环境${NC}"
        return 1
    fi

    echo -e "${YELLOW}正在创建虚拟环境: $GOTUBE_VENV_DIR${NC}"
    "$(runtime_python_bin)" -m venv "$GOTUBE_VENV_DIR"
}

runtime_activate_venv() {
    if [ ! -f "$GOTUBE_VENV_DIR/bin/activate" ]; then
        echo -e "${RED}✗ 未找到虚拟环境: $GOTUBE_VENV_DIR${NC}"
        return 1
    fi

    # shellcheck disable=SC1091
    source "$GOTUBE_VENV_DIR/bin/activate"
}

runtime_install_python_deps() {
    runtime_activate_venv || return 1

    echo -e "${YELLOW}正在安装 Python 依赖...${NC}"
    pip install --upgrade pip >/dev/null 2>&1
    pip install -r "$PROJECT_DIR/requirements.txt"
}

runtime_python_dep_ready() {
    runtime_activate_venv || return 1
    python -c "import fastapi, uvicorn, yt_dlp, sqlalchemy" >/dev/null 2>&1
}

runtime_prod_dep_ready() {
    runtime_activate_venv || return 1
    python -c "import uvicorn" >/dev/null 2>&1
}

runtime_ensure_python_deps() {
    local mode="${1:-common}"

    if runtime_python_dep_ready; then
        if [ "$mode" != "prod" ] || runtime_prod_dep_ready; then
            return 0
        fi
    fi

    if [ "$GOTUBE_AUTO_INSTALL_DEPS" != "1" ]; then
        echo -e "${RED}✗ Python 依赖不完整${NC}"
        echo -e "${YELLOW}请先执行: $0 init${NC}"
        return 1
    fi

    runtime_install_python_deps
}

runtime_install_node_deps() {
    if [ ! -f "$PROJECT_DIR/package.json" ]; then
        echo -e "${YELLOW}未找到 package.json，跳过前端依赖安装${NC}"
        return 0
    fi

    echo -e "${YELLOW}正在安装前端依赖...${NC}"
    (cd "$PROJECT_DIR" && npm install --silent)
}

runtime_build_frontend() {
    if [ "$GOTUBE_BUILD_FRONTEND" != "1" ]; then
        return 0
    fi

    if [ ! -f "$PROJECT_DIR/build.js" ]; then
        echo -e "${YELLOW}未找到 build.js，跳过前端构建${NC}"
        return 0
    fi

    if [ ! -d "$PROJECT_DIR/node_modules" ]; then
        if [ "$GOTUBE_AUTO_INSTALL_DEPS" = "1" ]; then
            runtime_install_node_deps || return 1
        else
            echo -e "${RED}✗ 前端依赖未安装${NC}"
            echo -e "${YELLOW}请先执行: $0 init${NC}"
            return 1
        fi
    fi

    echo -e "${GREEN}正在构建前端资源...${NC}"
    (cd "$PROJECT_DIR" && node build.js)
}

runtime_doctor() {
    local mode="${1:-common}"

    runtime_load_common_config
    echo -e "${GREEN}GoTube 启动环境检查${NC}"
    runtime_print_summary

    if [ -f "$PROJECT_DIR/.env" ]; then
        echo -e "${GREEN}✓ 已找到 .env${NC}"
    else
        echo -e "${YELLOW}⚠ 未找到 .env，将使用默认值和环境变量${NC}"
    fi

    if runtime_has_python; then
        echo -e "${GREEN}✓ Python 可用${NC}"
    else
        echo -e "${RED}✗ Python 不可用${NC}"
        return 1
    fi

    if [ -f "$GOTUBE_VENV_DIR/bin/activate" ]; then
        echo -e "${GREEN}✓ 虚拟环境已存在${NC}"
    else
        echo -e "${YELLOW}⚠ 虚拟环境不存在${NC}"
    fi

    if [ "$mode" = "prod" ]; then
        if command -v node >/dev/null 2>&1; then
            echo -e "${GREEN}✓ Node.js 可用${NC}"
        else
            echo -e "${YELLOW}⚠ Node.js 不可用${NC}"
        fi

        if [ "$GOTUBE_BUILD_FRONTEND" = "1" ] && [ ! -f "$PROJECT_DIR/build.js" ]; then
            echo -e "${YELLOW}⚠ GOTUBE_BUILD_FRONTEND=1，但仓库中不存在 build.js${NC}"
        fi
    fi

    return 0
}

runtime_init() {
    local mode="${1:-common}"

    runtime_load_common_config
    runtime_ensure_venv || return 1
    runtime_install_python_deps || return 1

    if [ "$mode" = "prod" ] && [ "$GOTUBE_BUILD_FRONTEND" = "1" ]; then
        runtime_install_node_deps || return 1
        runtime_build_frontend || return 1
    fi

    echo -e "${GREEN}✓ 初始化完成${NC}"
}
