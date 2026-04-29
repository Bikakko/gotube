#!/bin/bash
#
# GoTube 开发版 → 生产版 升级脚本
# 用法: ./sync.sh
# 回滚: ./sync.sh --rollback
#

# ============ 回滚模式 ============
if [ "${1}" = "--rollback" ]; then
    PROD_PATH="/root/gotubeweb"
    BACKUP_DIR="${PROD_PATH}/gotube-backups"

    if [ ! -d "$BACKUP_DIR" ] || [ -z "$(ls -A "$BACKUP_DIR" 2>/dev/null)" ]; then
        echo "错误: 没有找到备份文件"
        exit 1
    fi

    echo "========================================="
    echo "  GoTube 版本回滚"
    echo "========================================="
    echo ""
    echo "可用备份:"
    echo ""

    i=0
    for d in $(ls -1dt "${BACKUP_DIR}"/*/); do
        i=$((i + 1))
        name=$(basename "$d")
        size=$(du -sh "$d" | cut -f1)
        echo "  ${i}. ${name} (${size})"
    done
    echo ""

    if [ "$i" -eq 0 ]; then
        echo "错误: 没有可用备份"
        exit 1
    fi

    if [ -n "${2}" ]; then
        choice="${2}"
    else
        read -p "选择要恢复的备份编号 (1-${i}): " choice
    fi

    BACKUPS=($(ls -1dt "${BACKUP_DIR}"/*/))
    idx=$((choice - 1))

    if [ -z "${BACKUPS[$idx]}" ]; then
        echo "错误: 无效选择"
        exit 1
    fi

    SELECTED="${BACKUPS[$idx]}"
    echo ""
    echo "将恢复: $(basename "$SELECTED")"
    echo "当前生产版将被覆盖。"
    echo ""

    read -p "确认回滚? (y/N): " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        echo "已取消"
        exit 0
    fi

    echo ""
    echo "[1/3] 停止服务..."
    systemctl stop gotube 2>/dev/null || true

    echo "[2/3] 恢复备份..."
    find "${PROD_PATH}" -mindepth 1 -maxdepth 1 ! -name "gotube-backups" -exec rm -rf {} +
    cp -a "${SELECTED}"/* "${PROD_PATH}/" 2>/dev/null || true
    cp -a "${SELECTED}"/.[!.]* "${PROD_PATH}/" 2>/dev/null || true

    echo "[3/3] 启动服务..."
    systemctl start gotube 2>/dev/null || true

    echo ""
    echo "========================================="
    echo "  回滚完成!"
    echo "========================================="
    echo "  恢复版本: $(basename "$SELECTED")"
    echo "  检查状态: sudo systemctl status gotube"
    echo ""
    exit 0
fi

# ============ 升级模式 ============

DEV_PATH="/root/gotube"
PROD_PATH="/root/gotubeweb"
BACKUP_DIR="${PROD_PATH}/gotube-backups"
MAX_BACKUPS=5

echo "========================================="
echo "  GoTube 生产版升级"
echo "========================================="
echo ""

if [ ! -d "${DEV_PATH}" ]; then
    echo "错误: 开发目录不存在: ${DEV_PATH}"
    exit 1
fi

if [ ! -d "${PROD_PATH}" ]; then
    echo "错误: 生产目录不存在: ${PROD_PATH}"
    exit 1
fi

VERSION=$(head -1 "${DEV_PATH}/VERSION" 2>/dev/null || echo "unknown")
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="${BACKUP_DIR}/${TIMESTAMP}"

echo "开发版: ${DEV_PATH}"
echo "生产版: ${PROD_PATH}"
echo "备份:   ${BACKUP_PATH}"
echo "版本:   ${VERSION}"
echo ""

# ---- 只包含明确需要的生产文件 ----
# 白名单：精确指定哪些文件/目录要同步
PROD_FILES=(
    # 后端源码
    "server/__init__.py"
    "server/admin_api.py"
    "server/api.py"
    "server/config.py"
    "server/downloader.py"
    "server/main.py"
    "server/models.py"
    "server/queue_manager.py"
    # 前端源码
    "www/common.js"
    "www/download.html"
    "www/download.js"
    "www/favicon.jpg"
    "www/index.html"
    "www/watch.html"
    "www/admin/admin.html"
    "www/admin/css/admin.css"
    "www/admin/js/admin.js"
    "www/admin/js/auth.js"
    "www/admin/js/data.js"
    "www/admin/js/events.js"
    "www/admin/js/export.js"
    "www/admin/js/modals.js"
    "www/admin/js/render.js"
    "www/admin/js/state.js"
    "www/admin/js/toast.js"
    # 根目录配置
    ".env.example"
    "DEPLOYMENT.md"
    "GALLERY-HOME.md"
    "pyproject.toml"
    "requirements.txt"
    "README.md"
    "SECURITY-HARDENING.md"
    "SYSTEMD-SERVICE.md"
    "VERSION"
    "view_log.sh"
    "操作说明.md"
)

# ---- Step 1: 分析变更 ----
echo "[1/4] 正在分析变更..."

SAME=0
MOD=0
NEW=0
DEL_LIST=""
NEW_LIST=""
MOD_LIST=""

# 对比每个文件
for f in "${PROD_FILES[@]}"; do
    dev_file="${DEV_PATH}/${f}"
    prod_file="${PROD_PATH}/${f}"

    if [ -f "$dev_file" ]; then
        if [ -f "$prod_file" ]; then
            if cmp -s "$dev_file" "$prod_file"; then
                SAME=$((SAME + 1))
            else
                MOD=$((MOD + 1))
                MOD_LIST="${MOD_LIST}  [修改] ${f}\n"
            fi
        else
            NEW=$((NEW + 1))
            NEW_LIST="${NEW_LIST}  [新增] ${f}\n"
        fi
    fi
done

# 检查生产版中是否存在白名单以外的文件需要删除
cd "${PROD_PATH}"
PROD_EXISTING=$(find . -type f \
    ! -path "./gotube-backups/*" \
    ! -path "./gotube-backups" \
    | sed 's|^\./||' | sort)
cd - > /dev/null

DEL=0
for pf in $PROD_EXISTING; do
    found=0
    for f in "${PROD_FILES[@]}"; do
        if [ "$pf" = "$f" ]; then
            found=1
            break
        fi
    done
    if [ "$found" -eq 0 ]; then
        DEL=$((DEL + 1))
        DEL_LIST="${DEL_LIST}  [删除] ${pf}\n"
    fi
done

echo ""
echo "变更统计:"
echo "  未变更:  ${SAME} 个文件"
echo "  修改:    ${MOD} 个文件"
echo "  新增:    ${NEW} 个文件"
echo "  删除:    ${DEL} 个文件"
echo ""

if [ -n "$NEW_LIST" ] || [ -n "$DEL_LIST" ] || [ -n "$MOD_LIST" ]; then
    echo "变更详情:"
    [ -n "$MOD_LIST" ] && echo -ne "$MOD_LIST"
    [ -n "$NEW_LIST" ] && echo -ne "$NEW_LIST"
    [ -n "$DEL_LIST" ] && echo -ne "$DEL_LIST"
    echo ""
fi

read -p "确认执行升级? (y/N): " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "已取消"
    exit 0
fi

echo ""

# ---- Step 2: 备份 ----
echo "[2/4] 正在备份当前生产版..."
mkdir -p "${BACKUP_DIR}"

BACKUP_TMP=$(mktemp -d "${BACKUP_DIR}/.tmp_XXXXXX")
find "${PROD_PATH}" -mindepth 1 -maxdepth 1 ! -name "gotube-backups" -exec cp -a {} "${BACKUP_TMP}/" \; 2>/dev/null || true
mkdir -p "${BACKUP_PATH}"
mv "${BACKUP_TMP}"/* "${BACKUP_PATH}/" 2>/dev/null || true
rmdir "${BACKUP_TMP}" 2>/dev/null || true

echo "  备份完成: ${BACKUP_PATH}"

# 清理旧备份
BACKUP_COUNT=$(ls -1d "${BACKUP_DIR}"/*/ 2>/dev/null | wc -l)
if [ "$BACKUP_COUNT" -gt "$MAX_BACKUPS" ]; then
    DELETE_COUNT=$((BACKUP_COUNT - MAX_BACKUPS))
    echo "  清理 ${DELETE_COUNT} 个旧备份..."
    ls -1dt "${BACKUP_DIR}"/*/ | tail -n "$DELETE_COUNT" | xargs rm -rf
fi

echo ""

# ---- Step 3: 同步 ----
echo "[3/4] 正在同步文件..."

# 1. 删除白名单以外的文件
cd "${PROD_PATH}"
PROD_EXISTING=$(find . -type f \
    ! -path "./gotube-backups/*" \
    ! -path "./gotube-backups" \
    | sed 's|^\./||')
cd - > /dev/null

for pf in $PROD_EXISTING; do
    found=0
    for f in "${PROD_FILES[@]}"; do
        if [ "$pf" = "$f" ]; then
            found=1
            break
        fi
    done
    if [ "$found" -eq 0 ]; then
        rm -f "${PROD_PATH}/${pf}"
    fi
done

# 清理空目录
find "${PROD_PATH}" -mindepth 1 -type d -empty ! -path "${BACKUP_DIR}" -delete 2>/dev/null || true

# 2. 复制/更新白名单文件
for f in "${PROD_FILES[@]}"; do
    dev_file="${DEV_PATH}/${f}"
    prod_file="${PROD_PATH}/${f}"
    if [ -f "$dev_file" ]; then
        target_dir=$(dirname "$prod_file")
        mkdir -p "$target_dir"
        cp -a "$dev_file" "$prod_file"
    fi
done

echo "  同步完成"
echo ""

# ---- Step 4: 完成 ----
echo "========================================="
echo "  升级完成!"
echo "========================================="
echo ""
echo "后续步骤:"
echo "  1. cd ${PROD_PATH} && pip install -r requirements.txt"
echo "  2. sudo systemctl restart gotube"
echo "  3. sudo systemctl status gotube"
echo ""
echo "备份路径: ${BACKUP_PATH}"
echo "回滚命令: ./sync.sh --rollback"
echo ""
