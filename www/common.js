/**
 * GoTube - 公共 JS 工具函数
 * 管理页面和下载页共享的基础函数
 */

// ========== 基础工具函数 ==========

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
        'user': '普通用户',
        'readonly': '只读用户'
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
    // 如果是 /7777/admin，则 API 路径为 /7777/admin/api
    if (pathname.includes('/admin')) {
        const match = pathname.match(/^(\/[^\/]+\/admin)/);
        if (match) return match[1] + '/api';
    }
    return '/api';
}

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
        localStorage.removeItem('gotube_admin_token');
        throw new Error('UNAUTHORIZED');
    }
    
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: '请求失败' }));
        throw new Error(error.detail || `HTTP ${response.status}`);
    }
    
    // 如果是下载响应（zip/json/m3u8），返回 response 对象
    if (options.rawResponse) {
        return response;
    }
    
    return response.json();
}

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
