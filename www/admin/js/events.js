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
 * 标签输入框键盘事件
 */
function handleTagInputKeydown(e) {
    if (e.key === 'Enter') {
        e.preventDefault();
        const input = e.target;
        const tag = input.value.trim();

        if (tag && !state.filters.tags.includes(tag)) {
            state.filters.tags.push(tag);
            input.value = '';
            window.renderSelectedTags();
            state.pagination.page = 1;
            window.loadVideos();
        }
    }
}

/**
 * 移除筛选标签
 */
function removeFilterTag(tag) {
    state.filters.tags = state.filters.tags.filter(t => t !== tag);
    window.renderSelectedTags();
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
    window.updateBatchBar();
}

/**
 * 清空选择
 */
function clearSelection() {
    state.selectedVideos.clear();
    window.updateBatchBar();

    // 取消所有复选框
    document.querySelectorAll('.video-checkbox').forEach(cb => {
        cb.checked = false;
    });
}

/**
 * 切换下拉菜单
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
window.handleTagInputKeydown = handleTagInputKeydown;
window.removeFilterTag = removeFilterTag;
window.toggleVideoSelection = toggleVideoSelection;
window.clearSelection = clearSelection;
window.toggleDropdown = toggleDropdown;
window.hideAllDropdowns = hideAllDropdowns;
