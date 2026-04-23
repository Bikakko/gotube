/**
 * GoTube Admin - 全局状态管理
 */

let state = {
    currentUser: null,
    nav: {
        current: 'overview',
    },

    videos: [],
    filteredVideos: [],
    allSources: [],
    cachedAllSources: [],
    stats: null,
    selectedVideos: new Set(),
    filters: {
        keyword: '',
        source: '',
        time: 'all',
        owner: 'all',
        ownerSearchKeyword: '',
    },
    pagination: {
        page: 1,
        perPage: 20,
        total: 0,
        totalPages: 0,
    },

    users: [],
    usersLoaded: false,
    userSearchKeyword: '',
    userStatusFilter: 'all',
    userRoleFilter: 'all',
    invites: [],
    invitesLoaded: false,
    inviteView: 'active',

    overview: {
        ready: false,
    },
    userLibrary: {
        user: null,
        items: [],
        loading: false,
    },
    system: {
        ready: false,
        loading: false,
        cookieStatus: null,
        runtimeHealth: null,
        logView: 'app',
        appLogs: null,
        accessLogs: null,
    },

    isTransitioning: false,
};

function goToPage(page) {
    state.pagination.page = page;
    window.loadVideos();
}

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

function invalidateUserCache() {
    state.users = [];
    state.usersLoaded = false;
}

function invalidateInviteCache() {
    state.invites = [];
    state.invitesLoaded = false;
}

window.invalidateVideoCache = invalidateVideoCache;
window.invalidateUserCache = invalidateUserCache;
window.invalidateInviteCache = invalidateInviteCache;
