async function api() {
    if (!window.pywebview?.api) {
        throw new Error('桌面 API 未就绪');
    }
    return window.pywebview.api;
}

function setText(selector, value) {
    document.querySelector(selector).textContent = value || '';
}

async function loadConfig() {
    const bridge = await api();
    const config = await bridge.get_config();
    document.querySelector('#download-dir').value = config.download_dir || '';
    document.querySelector('#ffmpeg-path').value = config.ffmpeg_path || '';
}

async function saveConfig() {
    const bridge = await api();
    await bridge.set_download_dir(document.querySelector('#download-dir').value.trim());
    await bridge.set_ffmpeg_path(document.querySelector('#ffmpeg-path').value.trim());
    await loadConfig();
    setText('#tools-status', '设置已保存');
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
        meta.textContent = `${task.status || 'pending'} · ${Math.round(task.percent || 0)}%`;

        const file = document.createElement('div');
        file.className = 'task-file';
        file.textContent = task.file_path || task.error || '';

        card.append(title, meta, file);
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
    document.querySelector('#detect-tools-button').addEventListener('click', detectTools);
    document.querySelector('#upgrade-ytdlp-button').addEventListener('click', upgradeYtdlp);
    document.querySelector('#download-button').addEventListener('click', createDownload);

    loadConfig().catch((error) => setText('#log-output', error.message));
    refreshTasks().catch((error) => setText('#log-output', error.message));
    refreshLogs().catch(() => {});
    setInterval(refreshTasks, 1200);
    setInterval(refreshLogs, 2000);
});
