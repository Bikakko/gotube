/**
 * GoTube Admin - 导出功能模块
 * ZIP、JSON、m3u8 导出
 */

import { apiFetch } from '../../shared/common.module.js';
import { state } from './state.js';

/**
 * 导出 ZIP
 */
async function handleExportZip() {
    const useAll = state.selectedVideos.size === 0;

    try {
        const response = await apiFetch('/export/zip', {
            method: 'POST',
            body: JSON.stringify({
                all: useAll,
                filenames: useAll ? [] : Array.from(state.selectedVideos),
            }),
            rawResponse: true,
        });

        // 触发下载
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'gotube_export.zip';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
    } catch (err) {
        console.error('导出 ZIP 失败:', err);
        alert('导出 ZIP 失败: ' + err.message);
    }
}

/**
 * 导出 m3u8
 */
async function handleExportM3u8() {
    const useAll = state.selectedVideos.size === 0;

    try {
        const response = await apiFetch('/export/m3u8', {
            method: 'POST',
            body: JSON.stringify({
                all: useAll,
                filenames: useAll ? [] : Array.from(state.selectedVideos),
            }),
            rawResponse: true,
        });

        // 触发下载
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'gotube_playlist.m3u8';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
    } catch (err) {
        console.error('导出 m3u8 失败:', err);
        alert('导出 m3u8 失败: ' + err.message);
    }
}

export { handleExportZip, handleExportM3u8 };
