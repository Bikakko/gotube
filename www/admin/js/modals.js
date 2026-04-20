/**
 * GoTube Admin - 模态框模块
 * 播放器、分享、标签管理器、删除确认等模态框
 */

/**
 * 显示播放器模态框
 */
function showPlayerModal(video) {
    console.log('[Player] video object:', JSON.stringify(video));
    console.log('[Player] video.file_hash:', video.file_hash);
    const videoSrc = `/watch?v=${encodeURIComponent(video.file_hash)}`;
    console.log('[Player] video src URL:', videoSrc);

    const overlay = el('div', { className: 'modal active', id: 'player-modal' }, [
        el('div', { className: 'modal-content' }, [
            el('div', { className: 'modal-header' }, [
                el('div', {
                    className: 'modal-title',
                    textContent: video.title || '未命名视频',
                }),
                el('button', {
                    className: 'modal-close',
                    textContent: '×',
                    onClick: () => closeModal('player-modal'),
                }),
            ]),
            el('div', { className: 'modal-body' }, [
                el('video', {
                    id: 'player-video',
                    controls: true,
                    autoplay: true,
                }, [
                    el('source', {
                        src: videoSrc,
                        type: 'video/mp4',
                    }),
                ]),
            ]),
        ]),
    ]);

    // 点击背景关闭
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
            closeModal('player-modal');
        }
    });

    document.body.appendChild(overlay);

    // 自动聚焦到 video 元素，使浏览器能处理所有键盘操作（空格暂停、方向键快进快退）
    const videoEl = overlay.querySelector('#player-video');
    if (videoEl) {
        videoEl.focus();
    }
}

/**
 * 显示分享模态框 - 直接复制链接并提示
 */
function showShareModal(video) {
    const shareUrl = `${window.location.origin}/watch?v=${video.file_hash}`;

    // 直接复制链接，不弹窗
    navigator.clipboard.writeText(shareUrl).then(() => {
        if (typeof showToast === 'function') {
            showToast('✅ 链接已复制到剪贴板', 'success');
        } else {
            alert('链接已复制到剪贴板');
        }
    }).catch(() => {
        // Fallback: 使用 execCommand 兼容旧浏览器
        const input = document.createElement('input');
        input.value = shareUrl;
        input.style.position = 'fixed';
        input.style.opacity = '0';
        document.body.appendChild(input);
        input.select();
        document.execCommand('copy');
        document.body.removeChild(input);

        if (typeof showToast === 'function') {
            showToast('✅ 链接已复制到剪贴板', 'success');
        } else {
            alert('链接已复制到剪贴板');
        }
    });
}

function showMediaDetailsModal(video) {
    const owners = Array.isArray(video.owners) ? video.owners : [];
    const sourceUrls = Array.isArray(video.source_urls) ? video.source_urls : [];

    const ownerList = owners.length
        ? el('div', { className: 'detail-list' }, owners.map(owner => (
            el('div', { className: 'detail-list-row' }, [
                el('span', {
                    className: 'detail-list-main',
                    textContent: `${owner.username}${owner.share_enabled ? ' · 已分享' : ''}`,
                }),
                el('span', {
                    className: 'detail-list-sub',
                    textContent: owner.saved_at ? new Date(owner.saved_at).toLocaleString('zh-CN') : '无保存时间',
                }),
            ])
        )))
        : el('div', { className: 'empty-state', textContent: '暂无拥有者' });

    const sourceList = sourceUrls.length
        ? el('div', { className: 'detail-list' }, sourceUrls.map(url => (
            el('div', { className: 'detail-list-row detail-list-row-block' }, [
                el('span', { className: 'detail-list-main detail-url', textContent: url }),
            ])
        )))
        : el('div', { className: 'empty-state', textContent: '暂无来源链接' });

    const overlay = el('div', { className: 'modal active', id: 'media-detail-modal' }, [
        el('div', { className: 'modal-content' }, [
            el('div', { className: 'modal-header' }, [
                el('div', {
                    className: 'modal-title',
                    textContent: video.title || '媒体详情',
                }),
                el('button', {
                    className: 'modal-close',
                    textContent: '×',
                    onClick: () => closeModal('media-detail-modal'),
                }),
            ]),
            el('div', { className: 'modal-body' }, [
                el('div', { className: 'detail-summary-grid' }, [
                    el('div', { className: 'system-panel-card' }, [
                        el('div', { className: 'overview-card-label', textContent: '文件大小' }),
                        el('div', { className: 'overview-card-value detail-value-sm', textContent: formatBytes(video.size || 0) }),
                    ]),
                    el('div', { className: 'system-panel-card' }, [
                        el('div', { className: 'overview-card-label', textContent: '拥有者' }),
                        el('div', { className: 'overview-card-value detail-value-sm', textContent: String(video.owner_count || 0) }),
                    ]),
                    el('div', { className: 'system-panel-card' }, [
                        el('div', { className: 'overview-card-label', textContent: '来源数' }),
                        el('div', { className: 'overview-card-value detail-value-sm', textContent: String(video.source_count || 0) }),
                    ]),
                    el('div', { className: 'system-panel-card' }, [
                        el('div', { className: 'overview-card-label', textContent: '状态' }),
                        el('div', { className: 'overview-card-value detail-value-sm', textContent: video.is_legacy ? '未归属' : '已归属' }),
                    ]),
                ]),
                el('div', { className: 'detail-columns' }, [
                    el('section', { className: 'detail-section' }, [
                        el('h3', { textContent: '拥有者' }),
                        ownerList,
                    ]),
                    el('section', { className: 'detail-section' }, [
                        el('h3', { textContent: '来源链接' }),
                        sourceList,
                    ]),
                ]),
            ]),
        ]),
    ]);

    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
            closeModal('media-detail-modal');
        }
    });

    document.body.appendChild(overlay);
}

/**
 * 关闭模态框
 */
function closeModal(modalId) {
    const modal = $(`#${modalId}`);
    if (modal) {
        // 如果是播放器模态框，先停止视频播放
        if (modalId === 'player-modal') {
            const videoEl = modal.querySelector('video');
            if (videoEl) {
                videoEl.pause();
                videoEl.src = ''; // 清空源确保完全停止
                videoEl.load();
            }
        }
        modal.remove();
    }
}

// 显式挂载到 window，确保全局可见性
window.showPlayerModal = showPlayerModal;
window.showShareModal = showShareModal;
window.showMediaDetailsModal = showMediaDetailsModal;
window.closeModal = closeModal;
