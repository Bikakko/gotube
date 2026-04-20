/**
 * GoTube Admin - 数据操作模块
 * 视频列表加载、删除、批量删除、标签更新
 */

/**
 * 加载视频列表
 */
async function loadVideos() {
    try {
        if (state.currentUser && state.currentUser.role === 'admin' && !state.usersLoaded) {
            try {
                state.users = await apiFetch('/users');
                state.usersLoaded = true;
            } catch (err) {
                console.warn('加载用户筛选数据失败:', err);
            }
        }

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
        if (state.filters.owner && state.filters.owner !== 'all') {
            if (state.filters.owner === 'legacy') {
                params.set('owner', 'legacy');
            } else if (state.filters.owner.startsWith('user:')) {
                params.set('owner_user_id', state.filters.owner.slice(5));
            }
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

        // 首次加载时渲染整个筛选栏，后续只更新下拉选项（避免搜索框失焦）
        if (!window._filtersRendered) {
            window.renderFilters();
            window._filtersRendered = true;
        } else {
            // 只更新下拉菜单选项，不重建整个筛选栏
            window.updateSourceDropdownOptions();
            window.updateTimeDropdownOptions();
            window.updateOwnerDropdownOptions();
        }

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

async function loadUserLibrary(userId) {
    return apiFetch(`/users/${userId}/library`);
}

async function loadRuntimeHealth() {
    return apiFetch('/runtime/health');
}

async function loadCookiesStatusData() {
    return apiFetch('/cookies/status');
}

/**
 * 删除单个视频（入口函数）
 */
async function handleDeleteVideo(filename) {
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
                    el('p', {
                        className: 'delete-warning-text',
                        textContent: video.media_asset_id
                            ? `维护性删除会从所有用户视频库移除此视频，并物理删除硬盘文件。当前关联 ${video.reference_count || 0} 个用户条目，无法恢复。`
                            : '此操作将永久删除以下视频及其所有元数据，无法恢复。',
                    }),
                    el('div', { className: 'video-preview' }, [
                        video.thumbnail
                            ? el('img', { className: 'preview-thumb', src: video.thumbnail, alt: '' })
                            : el('div', { className: 'preview-thumb-empty', textContent: '🎬' }),
                        el('div', { className: 'preview-info' }, [
                            el('p', { className: 'preview-title', textContent: video.title || '未命名视频' }),
                            el('p', { className: 'preview-meta', textContent: `大小: ${formatBytes(video.size)}` }),
                            el('p', { className: 'preview-meta', textContent: `下载时间: ${new Date(video.created_at).toLocaleString('zh-CN')}` }),
                            el('p', { className: 'preview-meta', textContent: `来源: ${video.source || 'Unknown'}` }),
                            el('p', { className: 'preview-meta', textContent: `归属: ${video.owner_username || '未归属'}` }),
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
                    textContent: video.media_asset_id ? '🗑️ 维护删除' : '🗑️ 确认删除',
                    onClick: () => executeDeleteVideo(video),
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
async function executeDeleteVideo(video) {
    const btn = $('#confirm-delete-btn');
    if (btn) {
        btn.disabled = true;
        btn.textContent = '删除中...';
    }

    try {
        const endpoint = video.media_asset_id
            ? `/media-assets/${encodeURIComponent(video.media_asset_id)}`
            : `/videos/${encodeURIComponent(video.filename)}`;
        await apiFetch(endpoint, {
            method: 'DELETE',
        });

        // 从选中列表中移除
        state.selectedVideos.delete(video.filename);

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

        // 重新加载视频列表和统计信息
        await window.loadVideos();
        await window.loadStats();

        // 更新 UI（在加载新数据后更新）
        window.updateSelectAllCheckbox();
        window.updateBatchBar();

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
window.loadUserLibrary = loadUserLibrary;
window.loadRuntimeHealth = loadRuntimeHealth;
window.loadCookiesStatusData = loadCookiesStatusData;
window.handleDeleteVideo = handleDeleteVideo;
window.showDeleteConfirmModal = showDeleteConfirmModal;
window.handleBatchDelete = handleBatchDelete;
