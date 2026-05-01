/**
 * GoTube - 公共 JS 工具函数
 * 管理页面和下载页共享的基础函数
 */

// ========== 基础工具函数 ==========

window.GoTube = window.GoTube || {};

window.GoTubeSession = window.GoTubeSession || (() => {
    const CLIENT_KEY = 'gotube_client_id';
    const AUTH_CLIENT_KEY = 'gotube_authenticated_client';
    const GUEST_KEY = 'gotube_guest_session_id';
    const AUTH_TOKEN_KEY = 'gotube_admin_token';

    function newClientId() {
        return 'c_' + Math.random().toString(36).substr(2, 9);
    }

    function newGuestSessionId() {
        return 'guest_' + Date.now().toString(36) + '_' + Math.random().toString(36).substring(2, 9);
    }

    function getDownloadClientId() {
        let clientId = sessionStorage.getItem(CLIENT_KEY);
        if (!clientId) {
            clientId = newClientId();
            sessionStorage.setItem(CLIENT_KEY, clientId);
        }
        return clientId;
    }

    function resetDownloadClient() {
        const clientId = newClientId();
        sessionStorage.setItem(CLIENT_KEY, clientId);
        return clientId;
    }

    function clearDownloadClient() {
        sessionStorage.removeItem(CLIENT_KEY);
        clearAuthenticatedClient();
    }

    function getGuestSessionId() {
        let sessionId = sessionStorage.getItem(GUEST_KEY);
        if (!sessionId) {
            sessionId = newGuestSessionId();
            sessionStorage.setItem(GUEST_KEY, sessionId);
        }
        return sessionId;
    }

    function rotateGuestSession() {
        const sessionId = newGuestSessionId();
        sessionStorage.setItem(GUEST_KEY, sessionId);
        return sessionId;
    }

    function dropLegacyGuestLocalStorage() {
        localStorage.removeItem(GUEST_KEY);
    }

    function markAuthenticatedClient() {
        sessionStorage.setItem(AUTH_CLIENT_KEY, '1');
    }

    function clearAuthenticatedClient() {
        sessionStorage.removeItem(AUTH_CLIENT_KEY);
    }

    function wasAuthenticatedClient() {
        return sessionStorage.getItem(AUTH_CLIENT_KEY) === '1';
    }

    function clearAuthState({ resetDownloadClient: shouldResetDownloadClient = false } = {}) {
        localStorage.removeItem(AUTH_TOKEN_KEY);
        clearAuthenticatedClient();
        if (shouldResetDownloadClient) {
            return resetDownloadClient();
        }
        clearDownloadClient();
        return '';
    }

    return {
        getDownloadClientId,
        resetDownloadClient,
        clearDownloadClient,
        getGuestSessionId,
        rotateGuestSession,
        dropLegacyGuestLocalStorage,
        markAuthenticatedClient,
        clearAuthenticatedClient,
        wasAuthenticatedClient,
        clearAuthState,
    };
})();
window.GoTube.session = window.GoTubeSession;

/**
 * querySelector 快捷方式
 */
const $ = (sel, parent = document) => parent.querySelector(sel);

/**
 * querySelectorAll 快捷方式（返回数组）
 */
const $$ = (sel, parent = document) => [...parent.querySelectorAll(sel)];

/**
 * 创建 DOM 元素
 * @param {string} tag - 标签名
 * @param {object} attrs - 属性对象
 * @param {array|string} children - 子元素
 * @returns {HTMLElement} 创建的元素
 */
function el(tag, attrs = {}, children = []) {
    const elem = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
        if (k === 'className') elem.className = v;
        else if (k === 'innerHTML') elem.innerHTML = v;
        else if (k === 'textContent') elem.textContent = v;
        else if (k === 'checked') elem.checked = v;
        else if (k.startsWith('on')) elem.addEventListener(k.slice(2).toLowerCase(), v);
        else elem.setAttribute(k, v);
    }
    (Array.isArray(children) ? children : [children]).forEach(c => {
        if (typeof c === 'string') elem.appendChild(document.createTextNode(c));
        else if (c) elem.appendChild(c);
    });
    return elem;
}

/**
 * 格式化文件大小
 */
function formatBytes(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, i)).toFixed(1) + ' ' + sizes[i];
}

/**
 * 格式化下载速度
 */
function formatSpeed(bps) {
    return bps ? formatBytes(bps) + '/s' : '';
}

/**
 * 格式化剩余时间
 */
function formatETA(sec) {
    if (!sec) return '';
    const m = Math.floor(sec / 60), s = sec % 60;
    return m > 0 ? `${m}分${s}秒` : `${s}秒`;
}

/**
 * XSS 防护 - HTML 转义
 */
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
}

/**
 * 从 URL 提取来源平台
 */
function extractSource(url) {
    try {
        const hostname = new URL(url).hostname;
        if (hostname.includes('youtube.com') || hostname.includes('youtu.be')) return 'YouTube';
        if (hostname.includes('bilibili.com') || hostname.includes('b23.tv')) return 'Bilibili';
        if (hostname.includes('twitter.com') || hostname.includes('x.com')) return 'Twitter/X';
        if (hostname.includes('douyin.com')) return '抖音';
        if (hostname.includes('acfun.cn')) return 'AcFun';
        if (hostname.includes('iqiyi.com')) return '爱奇艺';
        if (hostname.includes('youku.com')) return '优酷';
        if (hostname.includes('qq.com')) return '腾讯视频';
        if (hostname.includes('kuaishou.com')) return '快手';
        return hostname;
    } catch {
        return 'Unknown';
    }
}

function formatRole(role) {
    const map = {
        'admin': '管理员',
        'user': '普通用户'
    };
    return map[role] || role;
}

/**
 * 获取 API 基础路径
 */
function getApiBase() {
    // 优先使用后端注入的隐藏路径
    if (window.GOTUBE_HIDDEN_PATH) {
        return `/${window.GOTUBE_HIDDEN_PATH}/admin/api`;
    }

    // 从当前页面 URL 推断
    const pathname = window.location.pathname;
    // 如果是 /<hidden>/admin，则 API 路径为 /<hidden>/admin/api
    if (pathname.includes('/admin')) {
        const match = pathname.match(/^(\/[^\/]+\/admin)/);
        if (match) return match[1] + '/api';
    }
    return '/api';
}
window.GoTube.resolveHiddenPath = function resolveHiddenPath(pathname = window.location.pathname, injectedHiddenPath = window.GOTUBE_HIDDEN_PATH) {
    if (injectedHiddenPath) return injectedHiddenPath;
    const parts = String(pathname || '').split('/').filter(Boolean);
    return parts[0] || '';
};

function attachVideoKeyboardControls(video, options = {}) {
    if (!video) return () => {};
    const seekSeconds = Number(options.seekSeconds || 5);
    const volumeStep = Number(options.volumeStep || 0.1);
    const isActive = typeof options.isActive === 'function' ? options.isActive : () => true;
    const wheelTarget = options.wheelTarget || video;
    const feedbackTarget = options.feedbackTarget || wheelTarget || video.parentElement || video;
    let volumeHudTimer = null;

    video.tabIndex = 0;

    function ensureHudHost(target) {
        const host = target instanceof HTMLElement ? target : video.parentElement || video;
        if (host instanceof HTMLElement) {
            const computed = window.getComputedStyle(host);
            if (computed.position === 'static') {
                host.style.position = 'relative';
            }
        }
        return host;
    }

    function ensureVolumeHud(target) {
        const host = ensureHudHost(target);
        if (!(host instanceof HTMLElement)) return null;
        let hud = host.querySelector('.gotube-volume-hud');
        if (!hud) {
            hud = document.createElement('div');
            hud.className = 'gotube-volume-hud';
            hud.style.cssText = [
                'position:absolute',
                'right:14px',
                'bottom:18px',
                'display:flex',
                'align-items:center',
                'gap:8px',
                'padding:6px 10px',
                'border-radius:999px',
                'background:rgba(15,23,42,0.78)',
                'color:#f8fafc',
                'box-shadow:0 10px 30px rgba(0,0,0,0.28)',
                'backdrop-filter:blur(10px)',
                'opacity:0',
                'transform:translateY(6px)',
                'transition:opacity .18s ease, transform .18s ease',
                'pointer-events:none',
                'z-index:4',
                'font-size:12px',
                'font-weight:600',
            ].join(';');

            const icon = document.createElement('span');
            icon.className = 'gotube-volume-hud-icon';
            icon.textContent = '🔊';

            const track = document.createElement('div');
            track.className = 'gotube-volume-hud-track';
            track.style.cssText = [
                'width:88px',
                'height:6px',
                'border-radius:999px',
                'background:rgba(255,255,255,0.18)',
                'overflow:hidden',
            ].join(';');

            const fill = document.createElement('div');
            fill.className = 'gotube-volume-hud-fill';
            fill.style.cssText = [
                'width:0%',
                'height:100%',
                'border-radius:999px',
                'background:linear-gradient(90deg, #60a5fa 0%, #93c5fd 100%)',
                'transition:width .14s ease',
            ].join(';');

            const label = document.createElement('span');
            label.className = 'gotube-volume-hud-label';
            label.textContent = '100%';

            track.appendChild(fill);
            hud.append(icon, track, label);
            host.appendChild(hud);
        }
        return hud;
    }

    function showVolumeHud() {
        const hud = ensureVolumeHud(feedbackTarget);
        if (!hud) return;
        const icon = hud.querySelector('.gotube-volume-hud-icon');
        const fill = hud.querySelector('.gotube-volume-hud-fill');
        const label = hud.querySelector('.gotube-volume-hud-label');
        const nextVolume = video.muted ? 0 : Math.round((video.volume || 0) * 100);
        if (icon) icon.textContent = nextVolume === 0 ? '🔇' : nextVolume < 50 ? '🔉' : '🔊';
        if (fill) fill.style.width = `${nextVolume}%`;
        if (label) label.textContent = `${nextVolume}%`;
        hud.style.opacity = '1';
        hud.style.transform = 'translateY(0)';
        if (volumeHudTimer) {
            clearTimeout(volumeHudTimer);
        }
        volumeHudTimer = window.setTimeout(() => {
            hud.style.opacity = '0';
            hud.style.transform = 'translateY(6px)';
        }, 900);
    }

    function clampVolume(nextVolume) {
        video.volume = Math.max(0, Math.min(1, Math.round(nextVolume * 100) / 100));
        video.muted = video.volume === 0;
        showVolumeHud();
    }

    const handler = (event) => {
        if (!isActive()) return;
        const target = event.target;
        if (
            target instanceof HTMLInputElement ||
            target instanceof HTMLTextAreaElement ||
            target instanceof HTMLSelectElement ||
            (target && target.isContentEditable)
        ) {
            return;
        }

        if ((event.key === ' ' || event.code === 'Space') && event.repeat) {
            event.preventDefault();
            return;
        }
        if (event.key === ' ' || event.code === 'Space') {
            event.preventDefault();
            if (video.paused) {
                void video.play().catch(() => {});
            } else {
                video.pause();
            }
            return;
        }
        if (event.key === 'ArrowLeft') {
            event.preventDefault();
            video.currentTime = Math.max(0, (video.currentTime || 0) - seekSeconds);
            return;
        }
        if (event.key === 'ArrowRight') {
            event.preventDefault();
            video.currentTime = Math.min(video.duration || Number.MAX_SAFE_INTEGER, (video.currentTime || 0) + seekSeconds);
            return;
        }
        if (event.key === 'ArrowUp') {
            event.preventDefault();
            clampVolume(video.volume + volumeStep);
            return;
        }
        if (event.key === 'ArrowDown') {
            event.preventDefault();
            clampVolume(video.volume - volumeStep);
        }
    };

    const wheelHandler = (event) => {
        if (!isActive()) return;
        event.preventDefault();
        const delta = event.deltaY < 0 ? volumeStep : -volumeStep;
        clampVolume(video.volume + delta);
    };

    document.addEventListener('keydown', handler, true);
    wheelTarget.addEventListener('wheel', wheelHandler, { passive: false });
    return () => {
        if (volumeHudTimer) {
            clearTimeout(volumeHudTimer);
            volumeHudTimer = null;
        }
        document.removeEventListener('keydown', handler, true);
        wheelTarget.removeEventListener('wheel', wheelHandler);
        const hud = feedbackTarget instanceof HTMLElement ? feedbackTarget.querySelector('.gotube-volume-hud') : null;
        hud?.remove();
    };
}
window.GoTube.attachVideoKeyboardControls = attachVideoKeyboardControls;

/**
 * 带认证的 API 请求封装
 */
async function apiFetch(endpoint, options = {}) {
    const token = localStorage.getItem('gotube_admin_token');
    const headers = {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
    };
    
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    
    const response = await fetch(`${getApiBase()}${endpoint}`, {
        ...options,
        headers,
    });
    
    // 401 表示未授权，清除 token
    if (response.status === 401) {
        window.GoTubeSession.clearAuthState();
        throw new Error('UNAUTHORIZED');
    }
    
    if (!response.ok) {
        let errorMsg = '请求失败';
        try {
            const errorData = await response.json();
            errorMsg = errorData.detail || errorData.message || `HTTP ${response.status}`;
        } catch (e) {
            errorMsg = `HTTP ${response.status} - ${response.statusText}`;
        }
        throw new Error(errorMsg);
    }
    
    // 如果是下载响应（zip/json/m3u8），返回 response 对象
    if (options.rawResponse) {
        return response;
    }
    
    return response.json();
}

window.GoTube.utils = {
    $,
    $$,
    el,
    formatBytes,
    formatSpeed,
    formatETA,
    escapeHtml,
    extractSource,
    formatRole,
    getApiBase,
    apiFetch,
};

// ========== 样式注入 ==========

/**
 * 样式注入
 */
function injectStyles() {
    if (document.querySelector('link[data-gotube-css]')) return; // 避免重复加载

    // 动态加载外部 CSS 文件
    const link = el('link', {
        rel: 'stylesheet',
        type: 'text/css',
        href: `/static/admin/css/admin.css?v=${Date.now()}`, // 使用时间戳强制刷新缓存
        'data-gotube-css': '',
    });
    document.head.appendChild(link);
}
