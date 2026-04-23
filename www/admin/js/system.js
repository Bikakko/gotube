/**
 * GoTube Admin - 系统页
 * 收口运行健康检查与 Cookie 状态
 */

async function loadSystemPage(forceReload = false) {
    if (!forceReload && state.system.ready && state.nav.current === 'system') {
        renderSystemPanels();
        return;
    }

    state.system.loading = true;
    renderSystemPanels();

    const [runtimeResult, cookieResult, appLogResult, accessLogResult] = await Promise.allSettled([
        window.loadRuntimeHealth(),
        window.loadCookiesStatusData(),
        window.loadRuntimeLogsData('app'),
        window.loadRuntimeLogsData('access'),
    ]);

    state.system.runtimeHealth = runtimeResult.status === 'fulfilled'
        ? runtimeResult.value
        : { error: runtimeResult.reason?.message || '运行巡检加载失败' };
    state.system.cookieStatus = cookieResult.status === 'fulfilled'
        ? cookieResult.value
        : { error: cookieResult.reason?.message || 'Cookie 状态加载失败' };
    state.system.appLogs = appLogResult.status === 'fulfilled'
        ? appLogResult.value
        : { error: appLogResult.reason?.message || '应用日志加载失败', type: 'app', lines: [] };
    state.system.accessLogs = accessLogResult.status === 'fulfilled'
        ? accessLogResult.value
        : { error: accessLogResult.reason?.message || '访问日志加载失败', type: 'access', lines: [] };
    state.system.loading = false;
    state.system.ready = true;

    renderSystemPanels();
}

function renderSystemPanels() {
    renderRuntimeHealth();
    renderSystemCookieStatus();
    renderSystemLogs();
}

function renderRuntimeHealth() {
    const slot = $('#system-runtime-slot');
    if (!slot) return;

    const data = state.system.runtimeHealth;
    if (state.system.loading && !data) {
        slot.innerHTML = '<div class="loading">加载运行巡检中</div>';
        return;
    }
    if (!data) {
        slot.innerHTML = '<div class="empty-state">暂无运行巡检数据</div>';
        return;
    }
    if (data.error) {
        slot.innerHTML = `<div class="error">加载失败: ${data.error}</div>`;
        return;
    }

    const blockers = Array.isArray(data.blockers) ? data.blockers : [];
    const ffmpegText = data.ffmpeg_summary || (data.ffmpeg_available ? '已安装' : '未安装');
    const ytdlpText = data.yt_dlp_summary || '未安装';

    slot.innerHTML = '';
    slot.appendChild(el('div', { className: 'system-panel-grid' }, [
        createSystemSummaryCard('阻断项', String(blockers.length), blockers.length === 0 ? '当前未发现阻断项' : blockers.join(' / ')),
        createSystemSummaryCard('FFmpeg', ffmpegText, data.ffmpeg_available ? '运行环境已检测到 ffmpeg' : '请先安装 ffmpeg'),
        createSystemSummaryCard('yt-dlp', ytdlpText, data.yt_dlp_version ? '运行环境已检测到 yt-dlp' : '请先安装 yt-dlp'),
        createSystemSummaryCard('版本', data.version || '--', '当前运行版本'),
    ]));
}

function createSystemSummaryCard(title, value, description) {
    return el('article', { className: 'system-panel-card' }, [
        el('div', { className: 'overview-card-label', textContent: title }),
        el('div', { className: 'overview-card-value detail-value-sm', textContent: value }),
        el('p', { className: 'overview-card-desc', textContent: description }),
    ]);
}

function renderSystemCookieStatus() {
    const slot = $('#system-cookie-slot');
    if (!slot) return;

    const data = state.system.cookieStatus;
    if (state.system.loading && !data) {
        slot.innerHTML = '<div class="loading">加载 Cookie 状态中</div>';
        syncSystemCookieActions();
        return;
    }
    if (!data) {
        slot.innerHTML = '<div class="empty-state">暂无 Cookie 状态</div>';
        syncSystemCookieActions();
        return;
    }
    if (data.error) {
        slot.innerHTML = `<div class="error">加载失败: ${data.error}</div>`;
        syncSystemCookieActions(data);
        return;
    }

    if (typeof window.renderCookiesStatus === 'function') {
        window.renderCookiesStatus(slot, data, { context: 'system' });
    } else {
        slot.innerHTML = `<div class="empty-state">${data.has_cookies ? '已检测到 Cookie' : '未配置 Cookie'}</div>`;
    }
    syncSystemCookieActions(data);
}

function syncSystemCookieActions(data = null) {
    const uploadBtn = $('#system-cookie-upload-btn');
    const deleteBtn = $('#system-cookie-delete-btn');
    if (!uploadBtn || !deleteBtn) return;

    const hasCookies = Boolean(data && data.has_cookies);
    uploadBtn.textContent = hasCookies ? '更新 Cookie' : '上传 Cookie';
    deleteBtn.disabled = !hasCookies;
}

function getCurrentSystemLogs() {
    return state.system.logView === 'access' ? state.system.accessLogs : state.system.appLogs;
}

function renderSystemLogs() {
    const slot = $('#system-log-slot');
    if (!slot) return;

    const appTab = $('#system-log-tab-app');
    const accessTab = $('#system-log-tab-access');
    if (appTab) appTab.classList.toggle('active', state.system.logView !== 'access');
    if (accessTab) accessTab.classList.toggle('active', state.system.logView === 'access');

    const data = getCurrentSystemLogs();
    if (state.system.loading && !data) {
        slot.innerHTML = '<div class="loading">加载运行日志中</div>';
        return;
    }
    if (!data) {
        slot.innerHTML = `<div class="empty-state">${state.system.logView === 'access' ? '暂无访问日志' : '暂无应用日志'}</div>`;
        return;
    }
    if (data.error) {
        slot.innerHTML = `<div class="error">加载失败: ${data.error}</div>`;
        return;
    }

    const lines = Array.isArray(data.lines) ? data.lines : [];
    if (!lines.length) {
        slot.innerHTML = `<div class="empty-state">${state.system.logView === 'access' ? '暂无访问日志' : '暂无应用日志'}</div>`;
        return;
    }

    slot.innerHTML = '';
    const panel = el('div', { className: 'system-log-panel' }, [
        el('div', { className: 'system-log-meta', textContent: `${state.system.logView === 'access' ? '访问日志' : '应用日志'} · 最近 ${lines.length} 行` }),
        el('pre', { className: 'system-log-pre', textContent: lines.join('\n') }),
    ]);
    slot.appendChild(panel);
}

function switchSystemLogView(logView) {
    if (state.system.logView === logView) return;
    state.system.logView = logView;
    renderSystemLogs();
}

async function copySystemLogView() {
    const data = getCurrentSystemLogs();
    const lines = Array.isArray(data?.lines) ? data.lines : [];
    if (!lines.length) {
        showToast('当前日志为空', 'warning');
        return;
    }
    const text = lines.join('\n');
    try {
        if (navigator.clipboard?.writeText) {
            await navigator.clipboard.writeText(text);
        } else {
            const textarea = document.createElement('textarea');
            textarea.value = text;
            textarea.setAttribute('readonly', '');
            textarea.style.position = 'fixed';
            textarea.style.opacity = '0';
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            textarea.remove();
        }
        showToast('日志已复制', 'success');
    } catch (error) {
        showToast('复制日志失败', 'error');
    }
}

window.loadSystemPage = loadSystemPage;
window.renderSystemPanels = renderSystemPanels;
window.renderRuntimeHealth = renderRuntimeHealth;
window.switchSystemLogView = switchSystemLogView;
window.copySystemLogView = copySystemLogView;
