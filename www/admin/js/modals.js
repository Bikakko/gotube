/**
 * GoTube Admin - 模态框模块
 * 播放器、分享、媒体详情等弹窗
 */

function showPlayerModal(video) {
    const videoSrc = `/watch?v=${encodeURIComponent(video.file_hash)}`;
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
                    loop: true,
                }, [
                    el('source', {
                        src: videoSrc,
                        type: 'video/mp4',
                    }),
                ]),
            ]),
        ]),
    ]);

    overlay.addEventListener('click', (event) => {
        if (event.target === overlay) {
            closeModal('player-modal');
        }
    });

    document.body.appendChild(overlay);
    const videoEl = overlay.querySelector('#player-video');

    if (videoEl) {
        videoEl.loop = true;
        videoEl.focus();
    }
}

function showShareModal(video) {
    const shareId = video.share_token || video.file_hash;
    const shareUrl = `${window.location.origin}/watch?v=${encodeURIComponent(shareId)}`;

    const reportResult = (copied) => {
        if (typeof showToast !== 'function') return;
        showToast(
            copied ? '链接已复制到剪贴板' : '复制失败，请手动复制链接',
            copied ? 'success' : 'error'
        );
    };

    const fallbackCopy = () => {
        const input = document.createElement('input');
        input.value = shareUrl;
        input.style.position = 'fixed';
        input.style.opacity = '0';
        document.body.appendChild(input);
        input.focus();
        input.select();

        let copied = false;
        try {
            copied = document.execCommand('copy');
        } catch (_error) {
            copied = false;
        }

        document.body.removeChild(input);
        return copied;
    };

    try {
        if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
            navigator.clipboard.writeText(shareUrl)
                .then(() => reportResult(true))
                .catch(() => reportResult(fallbackCopy()));
            return;
        }
    } catch (_error) {
        // fall through to legacy copy path
    }

    reportResult(fallbackCopy());
}

function showMediaDetailsModal(video) {
    const owners = Array.isArray(video.owners) ? video.owners : [];
    const sourceUrls = Array.isArray(video.source_urls) ? video.source_urls : [];
    let showAllOwners = false;
    let showAllSources = false;

    const renderOwnerRow = (owner) => (
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
    );

    const renderSourceRow = (url) => (
        el('div', { className: 'detail-list-row detail-list-row-block' }, [
            el('span', { className: 'detail-list-main detail-url', textContent: url }),
        ])
    );

    function createSectionList(items, renderItem, emptyText, expanded, expandLabel) {
        if (!items.length) {
            return el('div', { className: 'empty-state', textContent: emptyText });
        }

        const visibleItems = expanded ? items : items.slice(0, 10);
        const wrapper = el('div', { className: 'detail-list-stack' });
        wrapper.appendChild(el('div', {
            className: `detail-list ${expanded ? 'detail-list-expanded' : 'detail-list-collapsed'}`,
        }, visibleItems.map(renderItem)));

        if (items.length > 10) {
            wrapper.appendChild(el('button', {
                className: 'btn btn-secondary detail-list-toggle',
                textContent: expanded ? '收起' : `${expandLabel} (${items.length})`,
            }));
        }

        return wrapper;
    }

    function renderLists() {
        const ownerHost = $('#media-detail-owners');
        const sourceHost = $('#media-detail-sources');
        if (!ownerHost || !sourceHost) return;

        ownerHost.innerHTML = '';
        sourceHost.innerHTML = '';

        ownerHost.appendChild(createSectionList(
            owners,
            renderOwnerRow,
            '暂无拥有者',
            showAllOwners,
            '展开全部'
        ));
        sourceHost.appendChild(createSectionList(
            sourceUrls,
            renderSourceRow,
            '暂无来源链接',
            showAllSources,
            '展开全部'
        ));

        const ownerToggle = ownerHost.querySelector('.detail-list-toggle');
        if (ownerToggle) {
            ownerToggle.addEventListener('click', () => {
                showAllOwners = !showAllOwners;
                renderLists();
            });
        }

        const sourceToggle = sourceHost.querySelector('.detail-list-toggle');
        if (sourceToggle) {
            sourceToggle.addEventListener('click', () => {
                showAllSources = !showAllSources;
                renderLists();
            });
        }
    }

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
                        el('div', { id: 'media-detail-owners' }),
                    ]),
                    el('section', { className: 'detail-section' }, [
                        el('h3', { textContent: '来源链接' }),
                        el('div', { id: 'media-detail-sources' }),
                    ]),
                ]),
            ]),
        ]),
    ]);

    overlay.addEventListener('click', (event) => {
        if (event.target === overlay) {
            closeModal('media-detail-modal');
        }
    });

    document.body.appendChild(overlay);
    renderLists();
}

function closeModal(modalId) {
    const modal = $(`#${modalId}`);
    if (modal) {
        if (modalId === 'player-modal') {
            const videoEl = modal.querySelector('video');
            if (videoEl) {
                videoEl.pause();
                videoEl.src = '';
                videoEl.load();
            }
        }
        modal.remove();
    }
}

window.showPlayerModal = showPlayerModal;
window.showShareModal = showShareModal;
window.showMediaDetailsModal = showMediaDetailsModal;
window.closeModal = closeModal;
