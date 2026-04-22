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

    const [runtimeResult, cookieResult] = await Promise.allSettled([
        window.loadRuntimeHealth(),
        window.loadCookiesStatusData(),
    ]);

    state.system.runtimeHealth = runtimeResult.status === 'fulfilled'
        ? runtimeResult.value
        : { error: runtimeResult.reason?.message || '运行巡检加载失败' };
    state.system.cookieStatus = cookieResult.status === 'fulfilled'
        ? cookieResult.value
        : { error: cookieResult.reason?.message || 'Cookie 状态加载失败' };
    state.system.loading = false;
    state.system.ready = true;

    renderSystemPanels();
}

function renderSystemPanels() {
    renderRuntimeHealth();
    renderSystemCookieStatus();
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
    const git = data.git || {};
    const ffmpegText = data.ffmpeg_available ? (data.ffmpeg_version || '已安装') : '未安装';
    const ytdlpText = data.yt_dlp_version || '未安装';

    slot.innerHTML = '';
    slot.appendChild(el('div', { className: 'system-panel-grid' }, [
        createSystemSummaryCard('阻断项', String(blockers.length), blockers.length === 0 ? '当前未发现阻断项' : blockers.join(' / ')),
        createSystemSummaryCard('FFmpeg', ffmpegText, data.ffmpeg_available ? '运行环境已检测到 ffmpeg' : '请先安装 ffmpeg'),
        createSystemSummaryCard('yt-dlp', ytdlpText, data.yt_dlp_version ? '运行环境已检测到 yt-dlp' : '请先安装 yt-dlp'),
        createSystemSummaryCard('Git', git.branch || '--', git.commit ? `当前提交 ${git.commit}` : '未检测到 git 信息'),
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

window.loadSystemPage = loadSystemPage;
window.renderSystemPanels = renderSystemPanels;
window.renderRuntimeHealth = renderRuntimeHealth;
