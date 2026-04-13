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
 * 显示标签管理模态框
 */
function showTagManagerModal(video) {
    hideAllDropdowns();

    const currentTags = [...(video.tags || [])];

    const overlay = el('div', { className: 'modal active', id: 'tag-modal' }, [
        el('div', { className: 'modal-content' }, [
            el('div', { className: 'modal-header' }, [
                el('div', { className: 'modal-title', textContent: '管理标签' }),
                el('button', {
                    className: 'modal-close',
                    textContent: '×',
                    onClick: () => closeModal('tag-modal'),
                }),
            ]),
            el('div', { className: 'modal-body', id: 'tag-modal-body' }, [
                el('p', { textContent: '视频：' + (video.title || '未命名视频'), style: 'margin-bottom: 10px;' }),
                el('div', { className: 'tag-input-container', id: 'tag-modal-tags' }, [
                    ...currentTags.map(tag =>
                        el('span', { className: 'tag' }, [
                            document.createTextNode(tag),
                            el('span', {
                                className: 'tag-remove',
                                textContent: '×',
                                onClick: () => {
                                    const idx = currentTags.indexOf(tag);
                                    if (idx > -1) {
                                        currentTags.splice(idx, 1);
                                        renderModalTags(currentTags);
                                    }
                                },
                            }),
                        ])
                    ),
                ]),
                el('div', { style: 'margin-top: 10px; display: flex; gap: 8px;' }, [
                    el('input', {
                        className: 'tag-input',
                        id: 'tag-modal-input',
                        type: 'text',
                        placeholder: '输入标签回车添加...',
                        onKeyDown: (e) => {
                            if (e.key === 'Enter') {
                                e.preventDefault();
                                const input = e.target;
                                const tag = input.value.trim();
                                if (tag && !currentTags.includes(tag)) {
                                    currentTags.push(tag);
                                    input.value = '';
                                    renderModalTags(currentTags);
                                }
                            }
                        },
                    }),
                ]),
            ]),
            el('div', { className: 'modal-footer' }, [
                el('button', {
                    className: 'btn btn-primary',
                    textContent: '保存',
                    onClick: () => {
                        updateTags(video.filename, currentTags);
                        closeModal('tag-modal');
                    },
                }),
                el('button', {
                    className: 'btn btn-secondary',
                    textContent: '取消',
                    onClick: () => closeModal('tag-modal'),
                }),
            ]),
        ]),
    ]);

    // 点击背景关闭
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
            closeModal('tag-modal');
        }
    });

    document.body.appendChild(overlay);
}

/**
 * 渲染模态框中的标签
 */
function renderModalTags(tags) {
    const container = $('#tag-modal-tags');
    if (!container) return;

    // 清除现有标签
    container.innerHTML = '';

    // 重新渲染
    tags.forEach(tag => {
        container.appendChild(el('span', { className: 'tag' }, [
            document.createTextNode(tag),
            el('span', {
                className: 'tag-remove',
                textContent: '×',
                onClick: () => {
                    const idx = tags.indexOf(tag);
                    if (idx > -1) {
                        tags.splice(idx, 1);
                        renderModalTags(tags);
                    }
                },
            }),
        ]));
    });
}

/**
 * 关闭模态框
 */
function closeModal(modalId) {
    const modal = $(`#${modalId}`);
    if (modal) {
        modal.remove();
    }
}

// 显式挂载到 window，确保全局可见性
window.showPlayerModal = showPlayerModal;
window.showShareModal = showShareModal;
window.showTagManagerModal = showTagManagerModal;
window.renderModalTags = renderModalTags;
window.closeModal = closeModal;
