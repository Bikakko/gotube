/**
 * GoTube Admin - 事件处理模块
 * 筛选、标签、选择等事件处理
 */

/**
 * 关键词搜索变化
 */
function handleKeywordChange(keyword) {
    state.filters.keyword = keyword;
    state.pagination.page = 1;

    // 防抖：延迟 300ms 后加载
    clearTimeout(window._searchTimeout);
    window._searchTimeout = setTimeout(() => {
        window.loadVideos();
    }, 300);
}

/**
 * 来源筛选变化
 */
function handleSourceChange(source) {
    state.filters.source = source;
    state.pagination.page = 1;
    window.loadVideos();
}

/**
 * 时间筛选变化
 */
function handleTimeChange(time) {
    state.filters.time = time;
    state.pagination.page = 1;
    window.loadVideos();
}

/**
 * 归属筛选变化
 */
function handleOwnerChange(owner) {
    state.filters.owner = owner;
    state.pagination.page = 1;
    window.loadVideos();
}

/**
 * 切换视频选择状态
 */
function toggleVideoSelection(filename, selected) {
    if (selected) {
        state.selectedVideos.add(filename);
    } else {
        state.selectedVideos.delete(filename);
    }
    window.updateSelectAllCheckbox();
    window.updateBatchBar();
}

/**
 * 全选/取消全选
 */
function toggleSelectAll(selectAll) {
    if (selectAll) {
        // 全选当前页显示的所有视频
        state.filteredVideos.forEach(video => {
            state.selectedVideos.add(video.filename);
        });
    } else {
        // 取消全选：只取消当前页的视频，保留其他页的选择
        state.filteredVideos.forEach(video => {
            state.selectedVideos.delete(video.filename);
        });
    }
    window.updateSelectAllCheckbox();
    window.updateBatchBar();

    // 重新渲染视频网格以更新所有选择按钮状态
    window.renderVideoGrid();
}

/**
 * 更新全选复选框状态
 */
function updateSelectAllCheckbox() {
    const checkbox = $('#select-all-checkbox');
    if (!checkbox) return;

    const totalVideos = state.filteredVideos.length;
    const selectedCount = state.selectedVideos.size;

    if (totalVideos === 0) {
        checkbox.checked = false;
        checkbox.indeterminate = false;
    } else if (selectedCount === 0) {
        checkbox.checked = false;
        checkbox.indeterminate = false;
    } else if (selectedCount >= totalVideos) {
        checkbox.checked = true;
        checkbox.indeterminate = false;
    } else {
        checkbox.checked = false;
        checkbox.indeterminate = true; // 部分选中
    }
}

/**
 * 清空选择
 */
function clearSelection() {
    state.selectedVideos.clear();
    window.updateSelectAllCheckbox();
    window.updateBatchBar();

    // 重新渲染视频网格以更新所有选择按钮状态
    window.renderVideoGrid();
}

/**
 * 切换下拉菜单（仅用于导出菜单）
 */
function toggleDropdown(menuId) {
    const menu = $(`#${menuId}`);
    if (!menu) return;

    const isOpen = menu.classList.contains('show');

    // 先关闭所有菜单
    hideAllDropdowns();

    // 如果原来是关闭的，现在打开它
    if (!isOpen) {
        menu.classList.add('show');
    }
}

/**
 * 隐藏所有下拉菜单
 */
function hideAllDropdowns() {
    document.querySelectorAll('.dropdown-menu.show').forEach(menu => {
        menu.classList.remove('show');
    });
}

// 显式挂载到 window，确保全局可见性
window.handleKeywordChange = handleKeywordChange;
window.handleSourceChange = handleSourceChange;
window.handleTimeChange = handleTimeChange;
window.handleOwnerChange = handleOwnerChange;
window.toggleVideoSelection = toggleVideoSelection;
window.toggleSelectAll = toggleSelectAll;
window.updateSelectAllCheckbox = updateSelectAllCheckbox;
window.clearSelection = clearSelection;
window.toggleDropdown = toggleDropdown;
window.hideAllDropdowns = hideAllDropdowns;
