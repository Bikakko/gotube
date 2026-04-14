/**
 * GoTube Admin - 模态框模块
 * 播放器、分享、标签管理器、删除确认等模态框
 */

/**
 * 显示播放器模态框
 */
function showPlayerModal(video) {
    hideAllDropdowns();

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
 * 显示分享模态框
 */
function showShareModal(video) {
    hideAllDropdowns();

    const shareUrl = `${window.location.origin}/watch?v=${video.file_hash}`;

    const overlay = el('div', { className: 'modal active', id: 'share-modal' }, [
        el('div', { className: 'modal-content' }, [
            el('div', { className: 'modal-header' }, [
                el('div', { className: 'modal-title', textContent: '分享视频' }),
                el('button', {
                    className: 'modal-close',
                    textContent: '×',
                    onClick: () => closeModal('share-modal'),
                }),
            ]),
            el('div', { className: 'modal-body' }, [
                el('p', { textContent: '视频标题：' + (video.title || '未命名视频'), style: 'margin-bottom: 10px;' }),
                el('p', { textContent: '分享链接：', style: 'margin-bottom: 10px;' }),
                el('input', {
                    type: 'text',
                    value: shareUrl,
                    readonly: true,
                    id: 'share-link',
                    style: 'width: 100%; padding: 8px; border: 1px solid var(--border); background: var(--bg); color: var(--text); border-radius: 4px;',
                }),
            ]),
            el('div', { className: 'modal-footer' }, [
                el('button', {
                    className: 'btn btn-primary',
                    textContent: '复制链接',
                    onClick: () => {
                        const input = $('#share-link');
                        if (input) {
                            input.select();
                            document.execCommand('copy');
                            alert('链接已复制到剪贴板');
                        }
                    },
                }),
                el('button', {
                    className: 'btn btn-secondary',
                    textContent: '关闭',
                    onClick: () => closeModal('share-modal'),
                }),
            ]),
        ]),
    ]);

    // 点击背景关闭
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
            closeModal('share-modal');
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
window.closeModal = closeModal;
