async function api() {
    if (!window.pywebview?.api) {
        throw new Error('桌面 API 未就绪');
    }
    return window.pywebview.api;
}

function setText(selector, value) {
    document.querySelector(selector).textContent = value || '';
}

function formatTaskStatus(status) {
    const labels = {
        pending: '等待中',
        running: '下载中',
        completed: '已完成',
        failed: '失败',
        canceled: '已取消',
    };
    return labels[status] || status || '未知';
}

function formatTaskMeta(task) {
    const pieces = [
        formatTaskStatus(task.status),
        `${Math.round(task.percent || 0)}%`,
    ];
    if (task.speed) {
        pieces.push(task.speed);
    }
    if (task.eta) {
        pieces.push(`剩余 ${task.eta}`);
    }
    return pieces.join(' · ');
}

async function loadConfig() {
    const bridge = await api();
    const config = await bridge.get_config();
    document.querySelector('#download-dir').value = config.download_dir || '';
    document.querySelector('#ffmpeg-path').value = config.ffmpeg_path || '';
    document.querySelector('#browser-cookie-source').value = config.browser_cookie_source || 'edge';
}

async function loadAppInfo() {
    const bridge = await api();
    const info = await bridge.get_app_info();
    setText('#app-version', `v${info.version || 'unknown'}`);
}

async function saveConfig() {
    const bridge = await api();
    const result = await bridge.set_download_dir(document.querySelector('#download-dir').value.trim());
    if (!result.ok) {
        setText('#tools-status', result.message);
        await loadConfig();
        return;
    }
    await bridge.set_ffmpeg_path(document.querySelector('#ffmpeg-path').value.trim());
    await loadConfig();
    setText('#tools-status', result.message);
}

async function saveCookie() {
    const bridge = await api();
    const result = await bridge.save_cookie(document.querySelector('#cookie-content').value);
    setText('#tools-status', result.message);
}

async function deleteCookie() {
    const bridge = await api();
    const result = await bridge.delete_cookie();
    if (result.ok) {
        document.querySelector('#cookie-content').value = '';
        await loadConfig();
    }
    setText('#tools-status', result.message);
}

async function importBrowserCookie() {
    const bridge = await api();
    const browser = document.querySelector('#browser-cookie-source').value;
    const result = await bridge.import_browser_cookie(browser);
    await loadConfig();
    setText('#tools-status', result.message);
}

async function openDownloadDir() {
    const bridge = await api();
    const result = await bridge.open_download_dir();
    setText('#tools-status', result.ok ? `已打开：${result.path}` : '打开保存目录失败');
}

async function detectTools() {
    const bridge = await api();
    const result = await bridge.detect_tools();
    setText('#tools-status', JSON.stringify(result, null, 2));
}

function formatEnvironmentReport(result) {
    const lines = (result.checks || []).map((check) => {
        const label = check.ok ? '正常' : '缺失';
        const required = check.required ? '必需' : '可选';
        const detail = check.version || check.path || check.message || '';
        return `[${label}] ${check.name}（${required}）${detail}`;
    });
    if (result.missing_required) {
        lines.unshift('存在必需依赖缺失，请先安装桌面版依赖。');
    }
    return lines.join('\n');
}

async function detectEnvironment() {
    const bridge = await api();
    const result = await bridge.get_environment();
    setText('#tools-status', formatEnvironmentReport(result));
}

async function upgradeYtdlp() {
    const bridge = await api();
    const result = await bridge.upgrade_ytdlp();
    setText('#tools-status', JSON.stringify(result, null, 2));
}

async function createDownload() {
    const urlInput = document.querySelector('#download-url');
    const url = urlInput.value.trim();
    if (!url) return;

    const bridge = await api();
    const result = await bridge.create_download(url);
    setText('#log-output', result.message);
    urlInput.value = '';
    await refreshTasks();
}

async function cancelTask(taskId) {
    const bridge = await api();
    const result = await bridge.cancel_task(taskId);
    setText('#log-output', result.message);
    await refreshTasks();
}

async function openTaskLocation(taskId) {
    const bridge = await api();
    const result = await bridge.open_task_location(taskId);
    setText('#log-output', result.message);
}

async function clearFinishedTasks() {
    const bridge = await api();
    const result = await bridge.clear_finished_tasks();
    setText('#log-output', result.message);
    await refreshTasks();
}

async function refreshTasks() {
    const bridge = await api();
    const tasks = await bridge.get_tasks();
    renderTasks(tasks);
}

function renderTasks(tasks) {
    const list = document.querySelector('#task-list');
    list.replaceChildren();

    if (!tasks.length) {
        const empty = document.createElement('p');
        empty.className = 'empty-state';
        empty.textContent = '暂无下载任务';
        list.append(empty);
        return;
    }

    for (const task of tasks) {
        const card = document.createElement('article');
        card.className = 'task-card';

        const title = document.createElement('div');
        title.className = 'task-title';
        title.textContent = task.url || '未知链接';

        const meta = document.createElement('div');
        meta.className = 'task-meta';
        meta.textContent = formatTaskMeta(task);

        const file = document.createElement('div');
        file.className = 'task-file';
        file.textContent = task.file_path || task.error || '';

        card.append(title, meta, file);

        if (task.status === 'pending' || task.status === 'running') {
            const cancelButton = document.createElement('button');
            cancelButton.className = 'cancel-task-button';
            cancelButton.type = 'button';
            cancelButton.textContent = '取消';
            cancelButton.addEventListener('click', () => cancelTask(task.id));
            card.append(cancelButton);
        }
        if (task.status === 'completed') {
            const openButton = document.createElement('button');
            openButton.className = 'open-task-location-button';
            openButton.type = 'button';
            openButton.textContent = '打开位置';
            openButton.addEventListener('click', () => openTaskLocation(task.id));
            card.append(openButton);
        }
        list.append(card);
    }
}

async function refreshLogs() {
    const bridge = await api();
    const result = await bridge.get_logs();
    setText('#log-output', (result.lines || []).join('\n'));
}

document.addEventListener('DOMContentLoaded', () => {
    document.querySelector('#save-config-button').addEventListener('click', saveConfig);
    document.querySelector('#open-download-dir-button').addEventListener('click', openDownloadDir);
    document.querySelector('#save-cookie-button').addEventListener('click', saveCookie);
    document.querySelector('#delete-cookie-button').addEventListener('click', deleteCookie);
    document.querySelector('#import-browser-cookie-button').addEventListener('click', importBrowserCookie);
    document.querySelector('#detect-tools-button').addEventListener('click', detectTools);
    document.querySelector('#detect-environment-button').addEventListener('click', detectEnvironment);
    document.querySelector('#upgrade-ytdlp-button').addEventListener('click', upgradeYtdlp);
    document.querySelector('#download-button').addEventListener('click', createDownload);
    document.querySelector('#clear-finished-tasks-button').addEventListener('click', clearFinishedTasks);

    loadConfig().catch((error) => setText('#log-output', error.message));
    loadAppInfo().catch(() => {});
    refreshTasks().catch((error) => setText('#log-output', error.message));
    refreshLogs().catch(() => {});
    setInterval(refreshTasks, 1200);
    setInterval(refreshLogs, 2000);
});
