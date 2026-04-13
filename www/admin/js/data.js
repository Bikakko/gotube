/**
 * GoTube Admin - 数据操作模块
 * 视频列表加载、删除、批量删除、标签更新
 */

/**
 * 加载视频列表
 */
async function loadVideos() {
    try {
        const params = new URLSearchParams({
            page: state.pagination.page.toString(),
            per_page: state.pagination.perPage.toString(),
        });

        if (state.filters.keyword) {
            params.set('keyword', state.filters.keyword);
        }
        if (state.filters.source) {
            params.set('source', state.filters.source);
        }
        if (state.filters.time !== 'all') {
            params.set('time', state.filters.time);
        }
        if (state.filters.tags.length > 0) {
            params.set('tags', state.filters.tags.join(','));
        }

        const data = await apiFetch(`/videos?${params}`);

        state.videos = data.videos;
        state.filteredVideos = data.videos;
        state.allTags = data.all_tags || [];
        state.allSources = data.all_sources || [];
        state.pagination.total = data.total;
        state.pagination.totalPages = data.total_pages;
        state.pagination.page = data.page;

        // 重新渲染筛选栏（因为来源列表可能变化）
        window.renderFilters();

        // 重新渲染视频网格
        window.renderVideoGrid();

    } catch (err) {
        console.error('加载视频列表失败:', err);
        alert('加载视频列表失败: ' + err.message);
    }
}

/**
 * 加载统计信息
 */
async function loadStats() {
    try {
        state.stats = await apiFetch('/stats');
    } catch (err) {
        console.error('加载统计信息失败:', err);
        state.stats = null;
    }
}

/**
 * 删除单个视频（入口函数）
 */
async function handleDeleteVideo(filename) {
    hideAllDropdowns();

    // 查找视频信息
    const video = state.videos.find(v => v.filename === filename);
    if (!video) {
        showToast('视频信息未找到', 'error');
        return;
    }

    // 显示删除确认模态框
    showDeleteConfirmModal(video);
}

/**
 * 显示删除确认模态框
 */
function showDeleteConfirmModal(video) {
    const overlay = el('div', { className: 'modal active', id: 'delete-confirm-modal' }, [
        el('div', { className: 'modal-content modal-sm' }, [
            el('div', { className: 'modal-header' }, [
                el('div', { className: 'modal-title', textContent: '⚠️ 确认删除' }),
                el('button', {
                    className: 'modal-close',
                    textContent: '×',
                    onClick: () => closeModal('delete-confirm-modal'),
                }),
            ]),
            el('div', { className: 'modal-body' }, [
                el('div', { className: 'delete-confirm-content' }, [
                    el('p', { className: 'delete-warning-text', textContent: '此操作将永久删除以下视频及其所有元数据，无法恢复。' }),
                    el('div', { className: 'video-preview' }, [
                        video.thumbnail
                            ? el('img', { className: 'preview-thumb', src: video.thumbnail, alt: '' })
                            : el('div', { className: 'preview-thumb-empty', textContent: '🎬' }),
                        el('div', { className: 'preview-info' }, [
                            el('p', { className: 'preview-title', textContent: video.title || '未命名视频' }),
                            el('p', { className: 'preview-meta', textContent: `大小: ${formatBytes(video.size)}` }),
                            el('p', { className: 'preview-meta', textContent: `下载时间: ${new Date(video.created_at).toLocaleString('zh-CN')}` }),
                            el('p', { className: 'preview-meta', textContent: `来源: ${video.source || 'Unknown'}` }),
                        ]),
                    ]),
                ]),
            ]),
            el('div', { className: 'modal-footer' }, [
                el('button', {
                    className: 'btn btn-secondary',
                    textContent: '取消',
                    onClick: () => closeModal('delete-confirm-modal'),
                }),
                el('button', {
                    className: 'btn btn-danger',
                    id: 'confirm-delete-btn',
                    textContent: '🗑️ 确认删除',
                    onClick: () => executeDeleteVideo(video.filename),
                }),
            ]),
        ]),
    ]);

    // 点击背景关闭
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
            closeModal('delete-confirm-modal');
        }
    });

    document.body.appendChild(overlay);
}

/**
 * 执行删除视频操作
 */
async function executeDeleteVideo(filename) {
    const btn = $('#confirm-delete-btn');
    if (btn) {
        btn.disabled = true;
        btn.textContent = '删除中...';
    }

    try {
        await apiFetch(`/videos/${encodeURIComponent(filename)}`, {
            method: 'DELETE',
        });

        // 从选中列表中移除
        state.selectedVideos.delete(filename);

        // 关闭模态框
        closeModal('delete-confirm-modal');

        // 重新加载
        await loadVideos();
        await loadStats();

        showToast('视频删除成功', 'success');
    } catch (err) {
        console.error('删除视频失败:', err);
        showToast('删除视频失败: ' + err.message, 'error');

        if (btn) {
            btn.disabled = false;
            btn.textContent = '🗑️ 确认删除';
        }
    }
}

/**
 * 批量删除视频
 */
async function handleBatchDelete() {
    if (state.selectedVideos.size === 0) {
        showToast('请先选择要删除的视频', 'warning');
        return;
    }

    if (!confirm(`确定要删除选中的 ${state.selectedVideos.size} 个视频吗？此操作不可恢复。`)) {
        return;
    }

    const deleteBtn = $('#batch-delete-btn');
    if (deleteBtn) {
        deleteBtn.disabled = true;
        deleteBtn.textContent = '删除中...';
    }

    try {
        await apiFetch('/videos/batch-delete', {
            method: 'POST',
            body: JSON.stringify({
                filenames: Array.from(state.selectedVideos),
            }),
        });

        const count = state.selectedVideos.size;

        // 清空选中列表
        state.selectedVideos.clear();

        // 重新加载
        await window.loadVideos();
        await window.loadStats();

        showToast(`成功删除 ${count} 个视频`, 'success');
    } catch (err) {
        console.error('批量删除失败:', err);
        showToast('批量删除失败: ' + err.message, 'error');
    } finally {
        if (deleteBtn) {
            deleteBtn.disabled = false;
            deleteBtn.textContent = '🗑️ 批量删除';
        }
    }
}

/**
 * 更新视频标签
 */
async function updateTags(filename, tags) {
    try {
        await apiFetch(`/videos/${encodeURIComponent(filename)}/tags`, {
            method: 'PUT',
            body: JSON.stringify({ tags }),
        });

        // 重新加载视频列表
        await window.loadVideos();
    } catch (err) {
        console.error('更新标签失败:', err);
        alert('更新标签失败: ' + err.message);
    }
}

/**
 * 删除视频的某个标签
 */
function removeVideoTag(filename, tag) {
    const video = state.videos.find(v => v.filename === filename);
    if (!video) return;

    const newTags = (video.tags || []).filter(t => t !== tag);
    updateTags(filename, newTags);
}

// 显式挂载到 window，确保全局可见性
window.loadVideos = loadVideos;
window.loadStats = loadStats;
window.handleDeleteVideo = handleDeleteVideo;
window.showDeleteConfirmModal = showDeleteConfirmModal;
window.handleBatchDelete = handleBatchDelete;
window.updateTags = updateTags;
window.removeVideoTag = removeVideoTag;
