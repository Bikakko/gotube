/**
 * GoTube Admin - 全局状态管理
 * 所有模块共享的状态数据中心
 */

// ========== 全局状态 ==========
let state = {
    currentUser: null,
    currentView: 'videos', // 'videos', 'users' or 'invites'
    
    // 视频相关数据
    videos: [],
    filteredVideos: [],
    allSources: [],
    cachedAllSources: [],  // 缓存全局所有来源（不随筛选变化而减少）
    stats: null,
    selectedVideos: new Set(),
    filters: {
        keyword: '',
        source: '',
        time: 'all',
        owner: 'all',
    },
    pagination: {
        page: 1,
        perPage: 20,
        total: 0,
        totalPages: 0,
    },
    
    // 用户相关数据（缓存）
    users: [],
    usersLoaded: false, // 标记用户数据是否已加载过
    invites: [],
    invitesLoaded: false,
    
    // 视图切换动画状态
    isTransitioning: false,
};

// ========== 分页辅助函数 ==========

/**
 * 跳转到指定页
 */
function goToPage(page) {
    state.pagination.page = page;
    window.loadVideos();
}

// ========== 数据缓存辅助函数 ==========

/**
 * 使视频数据缓存失效（需要重新加载时调用）
 */
function invalidateVideoCache() {
    state.videos = [];
    state.filteredVideos = [];
    state.allSources = [];
    state.stats = null;
    state.pagination = {
        page: 1,
        perPage: 20,
        total: 0,
        totalPages: 0,
    };
}

/**
 * 使用户数据缓存失效
 */
function invalidateUserCache() {
    state.users = [];
    state.usersLoaded = false;
}

function invalidateInviteCache() {
    state.invites = [];
    state.invitesLoaded = false;
}

// 显式挂载到 window
window.invalidateVideoCache = invalidateVideoCache;
window.invalidateUserCache = invalidateUserCache;
window.invalidateInviteCache = invalidateInviteCache;
