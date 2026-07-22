/**
 * GoTube - 前端共享模块
 * 供 ES Module 页面复用，避免继续依赖全局脚本注入顺序。
 */

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

export function getDownloadClientId() {
    let clientId = sessionStorage.getItem(CLIENT_KEY);
    if (!clientId) {
        clientId = newClientId();
        sessionStorage.setItem(CLIENT_KEY, clientId);
    }
    return clientId;
}

export function resetDownloadClient() {
    const clientId = newClientId();
    sessionStorage.setItem(CLIENT_KEY, clientId);
    return clientId;
}

export function clearAuthenticatedClient() {
    sessionStorage.removeItem(AUTH_CLIENT_KEY);
}

export function clearDownloadClient() {
    sessionStorage.removeItem(CLIENT_KEY);
    clearAuthenticatedClient();
}

export function getGuestSessionId() {
    let sessionId = sessionStorage.getItem(GUEST_KEY);
    if (!sessionId) {
        sessionId = newGuestSessionId();
        sessionStorage.setItem(GUEST_KEY, sessionId);
    }
    return sessionId;
}

export function rotateGuestSession() {
    const sessionId = newGuestSessionId();
    sessionStorage.setItem(GUEST_KEY, sessionId);
    return sessionId;
}

export function dropLegacyGuestLocalStorage() {
    localStorage.removeItem(GUEST_KEY);
}

export function markAuthenticatedClient() {
    sessionStorage.setItem(AUTH_CLIENT_KEY, '1');
}

export function wasAuthenticatedClient() {
    return sessionStorage.getItem(AUTH_CLIENT_KEY) === '1';
}

export function clearAuthState({ resetDownloadClient: shouldResetDownloadClient = false } = {}) {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    clearAuthenticatedClient();
    if (shouldResetDownloadClient) {
        return resetDownloadClient();
    }
    clearDownloadClient();
    return '';
}

export const session = {
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

export const $ = (sel, parent = document) => parent.querySelector(sel);
export const $$ = (sel, parent = document) => [...parent.querySelectorAll(sel)];

export function el(tag, attrs = {}, children = []) {
    const elem = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
        if (k === 'className') elem.className = v;
        else if (k === 'innerHTML') elem.innerHTML = v;
        else if (k === 'textContent') elem.textContent = v;
        else if (k === 'checked') elem.checked = v;
        else if (k.startsWith('on')) elem.addEventListener(k.slice(2).toLowerCase(), v);
        else elem.setAttribute(k, v);
    }
    (Array.isArray(children) ? children : [children]).forEach((child) => {
        if (typeof child === 'string') elem.appendChild(document.createTextNode(child));
        else if (child) elem.appendChild(child);
    });
    return elem;
}

export function formatBytes(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, i)).toFixed(1) + ' ' + sizes[i];
}

export function formatSpeed(bps) {
    return bps ? formatBytes(bps) + '/s' : '';
}

export function formatETA(sec) {
    if (!sec) return '';
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return m > 0 ? `${m}分${s}秒` : `${s}秒`;
}

export function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
}

export function formatRole(role) {
    const map = {
        admin: '管理员',
        user: '普通用户',
    };
    return map[role] || role;
}

export function extractSource(url) {
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

export function getApiBase() {
    if (window.GOTUBE_HIDDEN_PATH) {
        return `/${window.GOTUBE_HIDDEN_PATH}/admin/api`;
    }
    const pathname = window.location.pathname;
    if (pathname.includes('/admin')) {
        const match = pathname.match(/^(\/[^\/]+\/admin)/);
        if (match) return match[1] + '/api';
    }
    return '/api';
}

export async function apiFetch(endpoint, options = {}) {
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
    if (response.status === 401) {
        clearAuthState();
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
    if (options.rawResponse) {
        return response;
    }
    return response.json();
}

export function injectStyles() {
    if (document.querySelector('link[data-gotube-css]')) return;
    const link = el('link', {
        rel: 'stylesheet',
        type: 'text/css',
        href: `/static/admin/css/admin.css?v=${Date.now()}`,
        'data-gotube-css': '',
    });
    document.head.appendChild(link);
}

export function resolveHiddenPath(pathname = window.location.pathname, injectedHiddenPath = window.GOTUBE_HIDDEN_PATH) {
    if (injectedHiddenPath) return injectedHiddenPath;
    const parts = String(pathname || '').split('/').filter(Boolean);
    return parts[0] || '';
}

export function attachVideoKeyboardControls(video, options = {}) {
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

const goTube = window.GoTube = window.GoTube || {};
goTube.session = session;
goTube.resolveHiddenPath = resolveHiddenPath;
goTube.attachVideoKeyboardControls = attachVideoKeyboardControls;
goTube.utils = {
    $,
    $$,
    el,
    formatBytes,
    formatSpeed,
    formatETA,
    escapeHtml,
    formatRole,
};
