/**
 * GoTube Admin - 全局状态管理
 * 所有模块共享的状态数据中心
 */

// ========== 全局状态 ==========
let state = {
    currentUser: null,
    currentView: 'videos', // 'videos' or 'users'
    videos: [],
    filteredVideos: [],
    allTags: [],
    allSources: [],
    stats: null,
    selectedVideos: new Set(),
    filters: {
        keyword: '',
        source: '',
        time: 'all',
        tags: [],
    },
    pagination: {
        page: 1,
        perPage: 20,
        total: 0,
        totalPages: 0,
    },
};

// ========== 分页辅助函数 ==========

/**
 * 跳转到指定页
 */
function goToPage(page) {
    state.pagination.page = page;
    window.loadVideos();
}
