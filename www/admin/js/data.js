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

        const data = await apiFetch(`/videos?${params}`);

        state.videos = data.videos;
        state.filteredVideos = data.videos;
        
        // 缓存全局所有来源：只在首次或来源列表变化时更新
        const newSources = data.all_sources || [];
        if (newSources.length > 0) {
            // 如果缓存为空，或者新来源包含缓存中没有的来源，则更新缓存
            if (state.cachedAllSources.length === 0) {
                state.cachedAllSources = newSources;
            } else {
                // 合并新来源到缓存中（去重）
                const merged = [...state.cachedAllSources];
                newSources.forEach(s => {
                    if (!merged.includes(s)) {
                        merged.push(s);
                    }
                });
                state.cachedAllSources = merged;
            }
        }
        // 始终使用缓存的来源列表
        state.allSources = state.cachedAllSources;
        
        state.pagination.total = data.total;
        state.pagination.totalPages = data.total_pages;
        state.pagination.page = data.page;

        // 重新渲染筛选栏（因为来源列表可能变化）
        window.renderFilters();

        // 重新渲染视频网格
        window.renderVideoGrid();

        // 更新批量操作栏
        window.updateBatchBar();

    } catch (err) {
        console.error('加载视频列表失败:', err);

        // 如果是 UNAUTHORIZED 错误，尝试刷新 token 或提示用户重新登录
        if (err.message === 'UNAUTHORIZED') {
            // 清除无效 token
            localStorage.removeItem('gotube_admin_token');

            // 显示友好的提示，而不是直接踢出
            if (typeof showToast === 'function') {
                showToast('登录已过期，请重新登录', 'error');
            } else {
                alert('登录已过期，请重新登录');
            }

            // 延迟后显示登录界面
            setTimeout(() => {
                if (typeof showLoginForm === 'function') {
                    showLoginForm();
                } else {
                    location.reload();
                }
            }, 1000);
        } else {
            // 其他错误，显示 Toast 提示
            if (typeof showToast === 'function') {
                showToast('加载视频列表失败: ' + err.message, 'error');
            } else {
                alert('加载视频列表失败: ' + err.message);
            }
        }
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
        const result = await apiFetch('/videos/batch-delete', {
            method: 'POST',
            body: JSON.stringify({
                filenames: Array.from(state.selectedVideos),
            }),
        });

        // 检查后端返回的结果
        const successCount = result.success || 0;
        const failedCount = result.failed || 0;
        const results = result.results || [];

        // 只从选中列表中移除成功的视频
        const successFilenames = results
            .filter(r => r.status === 'deleted')
            .map(r => r.filename);
        successFilenames.forEach(f => state.selectedVideos.delete(f));

        // 更新UI
        window.updateSelectAllCheckbox();
        window.updateBatchBar();

        // 重新加载视频列表
        await window.loadVideos();
        await window.loadStats();

        // 显示详细的删除结果
        if (failedCount > 0) {
            // 获取失败的文件名和原因
            const failedItems = results
                .filter(r => r.status !== 'deleted')
                .map(r => {
                    const name = r.filename.split('/').pop() || r.filename;
                    let reason = r.reason || '未知错误';
                    // 简化常见错误信息
                    if (reason.includes('WinError 32') || reason.includes('正在使用此文件')) {
                        reason = '文件被播放器占用，请先关闭播放器';
                    } else if (reason.includes('权限')) {
                        reason = '权限不足';
                    }
                    return `• ${name}: ${reason}`;
                });

            if (successCount > 0) {
                showToast(
                    `成功删除 ${successCount} 个，失败 ${failedCount} 个\n${failedItems.join('\n')}`,
                    'warning',
                    5000
                );
            } else {
                showToast(
                    `删除失败 (${failedCount} 个)\n${failedItems.join('\n')}`,
                    'error',
                    5000
                );
            }
        } else {
            showToast(`成功删除 ${successCount} 个视频`, 'success');
        }
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

// 显式挂载到 window，确保全局可见性
window.loadVideos = loadVideos;
window.loadStats = loadStats;
window.handleDeleteVideo = handleDeleteVideo;
window.showDeleteConfirmModal = showDeleteConfirmModal;
window.handleBatchDelete = handleBatchDelete;
