async function api() {
    if (!window.pywebview?.api) {
        throw new Error('桌面 API 未就绪');
    }
    return window.pywebview.api;
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
}

async function saveCookie() {
    const bridge = await api();
    const result = await bridge.save_cookie(document.querySelector('#cookie-content').value);
    document.querySelector('#tools-status').textContent = result.message;
}

async function detectTools() {
    const bridge = await api();
    const result = await bridge.detect_tools();
    document.querySelector('#tools-status').textContent = JSON.stringify(result, null, 2);
}

async function upgradeYtdlp() {
    const bridge = await api();
    const result = await bridge.upgrade_ytdlp();
    document.querySelector('#tools-status').textContent = JSON.stringify(result, null, 2);
}

async function createDownload() {
    const url = document.querySelector('#download-url').value.trim();
    if (!url) return;
    const bridge = await api();
    const result = await bridge.create_download(url);
    document.querySelector('#log-output').textContent = result.message;
}

document.addEventListener('DOMContentLoaded', () => {
    document.querySelector('#save-config-button').addEventListener('click', saveConfig);
    document.querySelector('#save-cookie-button').addEventListener('click', saveCookie);
    document.querySelector('#detect-tools-button').addEventListener('click', detectTools);
    document.querySelector('#upgrade-ytdlp-button').addEventListener('click', upgradeYtdlp);
    document.querySelector('#download-button').addEventListener('click', createDownload);
    loadConfig().catch((error) => {
        document.querySelector('#log-output').textContent = error.message;
    });
});
