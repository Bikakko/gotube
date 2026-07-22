/**
 * GoTube Admin - 页面渲染模块
 * 顶部导航、概览骨架、媒体筛选区、媒体网格、分页、批量操作栏
 */

import { $, el, formatBytes } from '../../shared/common.module.js';
import { state } from './state.js';
import { loadStats, handleDeleteVideo, handleBatchDelete, goToPage } from './data.js';
import { loadSystemPage, copySystemLogView, switchSystemLogView } from './system.js';
import { showCookiesManagement, deleteCookies } from './cookies.js';
import { updateSelectAllCheckbox, clearSelection } from './events.js';
import { showMediaDetailsModal, showShareModal, showPlayerModal } from './modals.js';
import { showToast } from './toast.js';
import { handleExportZip, handleExportM3u8 } from './export.js';

function getRoleLabel(role) {
    const map = {
        admin: '管理员',
        user: '普通用户',
    };
    return map[role] || role || '未知角色';
}

function formatDurationLabel(duration) {
    const totalSeconds = Math.max(0, Math.floor(Number(duration) || 0));
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;

    if (hours > 0) {
        return [hours, minutes, seconds].map((value) => String(value).padStart(2, '0')).join(':');
    }
    return [minutes, seconds].map((value) => String(value).padStart(2, '0')).join(':');
}

function formatUserIdentityText(user) {
    if (!user) return '未知用户';
    const displayName = user.display_name || user.username || '';
    return `账号：${user.username || '-'} | 昵称：${displayName} | ID：${user.id ?? '-'}`;
}

function findUserById(userId) {
    return (state.users || []).find((user) => Number(user.id) === Number(userId)) || null;
}

function getOwnerSummaryLabel(video) {
    if (video.is_legacy) return 'Legacy';
    const owner = findUserById(video.owner_user_id);
    return owner ? formatUserIdentityText(owner) : (video.owner_username || '未归属');
}

function ensureViewContainerVisible(view) {
    const containers = {
        overview: $('#overview-view-container'),
        media: $('#video-view-container'),
        users: $('#user-view-container'),
        invites: $('#invite-view-container'),
        system: $('#system-view-container'),
    };

    Object.entries(containers).forEach(([name, container]) => {
        if (!container) return;
        const active = name === view;
        container.hidden = !active;
        container.style.display = active ? 'block' : 'none';
    });
}

async function renderPage() {
    state.nav.current = 'overview';

    renderNavbar();
    renderMainLayout();
    await loadStats();
    renderOverviewSection();
    renderSystemSection();
    renderBatchBar();

    ensureViewContainerVisible('overview');
}

function renderNavbar() {
    const user = state.currentUser || { username: 'Unknown', role: 'user' };
    const brief = $('#admin-user-brief');
    if (!brief) return;

    brief.innerHTML = '';
    brief.appendChild(el('span', {
        className: 'admin-user-name',
        textContent: formatUserIdentityText(user),
    }));
    brief.appendChild(el('span', {
        className: `role-badge ${user.role || 'user'}`,
        textContent: getRoleLabel(user.role),
    }));

    document.querySelectorAll('[data-admin-nav]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.adminNav === state.nav.current);
    });
}

function renderMainLayout() {
    ensureViewContainerVisible(state.nav.current || 'overview');
}

function createOverviewCard(title, value, description) {
    return el('article', { className: 'overview-card' }, [
        el('div', { className: 'overview-card-label', textContent: title }),
        el('div', { className: 'overview-card-value', textContent: value }),
        el('p', { className: 'overview-card-desc', textContent: description }),
    ]);
}

function renderOverviewSection() {
    const container = $('#overview-view-container');
    if (!container) return;

    const stats = state.stats || {};
    const videoCount = typeof stats.total === 'number' ? String(stats.total) : '--';
    const totalSize = typeof stats.total_size === 'number' ? formatBytes(stats.total_size) : '--';
    const todayCount = stats.times && typeof stats.times.today === 'number' ? String(stats.times.today) : '--';
    const sourceCount = Array.isArray(stats.sources) ? String(stats.sources.length) : '--';

    container.innerHTML = '';
    container.appendChild(el('section', { className: 'admin-section' }, [
        el('div', { className: 'admin-section-header' }, [
            el('div', {}, [
                el('h2', { textContent: '概览' }),
            ]),
        ]),
        el('div', { className: 'overview-grid' }, [
            createOverviewCard('媒体总数', videoCount, '全局媒体按资产聚合后的结果。'),
            createOverviewCard('总占用', totalSize, '当前聚合媒体的物理文件占用。'),
            createOverviewCard('今日新增', todayCount, '基于媒体创建时间的当日统计。'),
            createOverviewCard('来源数', sourceCount, '已识别的平台来源数量。'),
        ]),
    ]));
}

function renderSystemSection() {
    const container = $('#system-view-container');
    if (!container) return;

    container.innerHTML = '';
    container.appendChild(el('section', { className: 'admin-section' }, [
        el('div', { className: 'admin-section-header' }, [
            el('div', {}, [
                el('h2', { textContent: '系统' }),
            ]),
            el('div', { className: 'admin-actions' }, [
                el('button', {
                    type: 'button',
                    className: 'btn btn-secondary',
                    textContent: '刷新系统状态',
                    onClick: () => loadSystemPage(true),
                }),
            ]),
        ]),
        el('div', { className: 'system-section-stack' }, [
            el('div', { className: 'system-block' }, [
                el('h3', { textContent: '运行巡检' }),
                el('div', { id: 'system-runtime-slot' }, [
                    el('div', { className: 'loading', textContent: '加载运行巡检中' }),
                ]),
            ]),
            el('div', { className: 'system-block system-cookie-block' }, [
                el('div', { className: 'system-block-header' }, [
                    el('div', {}, [
                        el('h3', { textContent: 'Cookie 管理' }),
                    ]),
                    el('div', { className: 'system-block-actions' }, [
                        el('button', {
                            type: 'button',
                            id: 'system-cookie-upload-btn',
                            className: 'btn btn-primary',
                            textContent: '上传 Cookie',
                            onClick: () => showCookiesManagement(),
                        }),
                        el('button', {
                            type: 'button',
                            id: 'system-cookie-delete-btn',
                            className: 'btn btn-danger',
                            textContent: '删除当前 Cookie',
                            onClick: () => deleteCookies(),
                            disabled: true,
                        }),
                    ]),
                ]),
                el('div', { id: 'system-cookie-slot' }, [
                    el('div', { className: 'loading', textContent: '加载 Cookie 状态中' }),
                ]),
            ]),
            el('div', { className: 'system-block system-log-block' }, [
                el('div', { className: 'system-block-header' }, [
                    el('div', {}, [
                        el('h3', { textContent: '运行日志' }),
                    ]),
                    el('div', { className: 'system-block-actions' }, [
                        el('button', {
                            type: 'button',
                            className: 'btn btn-secondary',
                            textContent: '刷新日志',
                            onClick: () => loadSystemPage(true),
                        }),
                        el('button', {
                            type: 'button',
                            className: 'btn btn-secondary',
                            textContent: '复制日志',
                            onClick: () => copySystemLogView(),
                        }),
                    ]),
                ]),
                el('div', { className: 'invite-view-tabs system-log-tabs' }, [
                    el('button', {
                        type: 'button',
                        className: 'invite-view-tab active',
                        id: 'system-log-tab-app',
                        textContent: '应用日志',
                        onClick: () => switchSystemLogView('app'),
                    }),
                    el('button', {
                        type: 'button',
                        className: 'invite-view-tab',
                        id: 'system-log-tab-access',
                        textContent: '访问日志',
                        onClick: () => switchSystemLogView('access'),
                    }),
                ]),
                el('div', { id: 'system-log-slot' }, [
                    el('div', { className: 'loading', textContent: '加载运行日志中' }),
                ]),
            ]),
        ]),
    ]));
}

function renderStatsPanel() {
    const slot = $('#stats-slot');
    if (!slot) return;

    slot.innerHTML = '';
    const statsPanel = el('div', { className: 'stats-panel', id: 'stats-panel' });

    if (!state.stats) {
        slot.appendChild(statsPanel);
        return;
    }

    const { total, total_size, sources, times } = state.stats;

    statsPanel.appendChild(el('div', { className: 'stat-card' }, [
        el('div', { className: 'stat-value', textContent: total }),
        el('div', { className: 'stat-label', textContent: '视频总数' }),
    ]));

    statsPanel.appendChild(el('div', { className: 'stat-card' }, [
        el('div', { className: 'stat-value', textContent: formatBytes(total_size) }),
        el('div', { className: 'stat-label', textContent: '总大小' }),
    ]));

    if (sources && sources.length > 0) {
        const topSource = sources[0];
        statsPanel.appendChild(el('div', { className: 'stat-card' }, [
            el('div', { className: 'stat-value', textContent: topSource.name }),
            el('div', { className: 'stat-label', textContent: `${topSource.count} 个 (${topSource.percentage}%)` }),
        ]));
    }

    statsPanel.appendChild(el('div', { className: 'stat-card' }, [
        el('div', { className: 'stat-value', textContent: times.today || 0 }),
        el('div', { className: 'stat-label', textContent: '今天' }),
    ]));

    slot.appendChild(statsPanel);
}

function renderFilters() {
    const slot = $('#filters-slot');
    if (!slot || state.nav.current !== 'media') return;

    slot.innerHTML = '';

    const filtersBar = el('div', { className: 'filters filters-toolbar', id: 'filters-bar' }, [
        el('div', { className: 'filter-cluster filter-cluster-primary' }, [
            el('div', { className: 'filter-group filter-group-compact' }, [
                el('input', {
                    type: 'checkbox',
                    id: 'select-all-checkbox',
                    title: '全选 / 取消全选',
                    checked: false,
                    'data-action': 'select-all',
                }),
                el('label', {
                    for: 'select-all-checkbox',
                    textContent: '全选',
                    style: 'cursor: pointer; font-size: 13px; color: var(--text-sec);',
                }),
            ]),
            el('div', { className: 'filter-group filter-group-search' }, [
                el('span', { className: 'filter-label', textContent: '搜索' }),
                el('input', {
                    className: 'search-input',
                    id: 'search-input',
                    type: 'text',
                    placeholder: '按标题搜索...',
                    value: state.filters.keyword,
                    'data-action': 'search-input',
                }),
            ]),
        ]),
        el('div', { className: 'filter-cluster filter-cluster-secondary' }, [
            el('div', { className: 'filter-group' }, [
                el('span', { className: 'filter-label', textContent: '来源' }),
                el('div', { className: 'custom-dropdown', id: 'source-dropdown' }, [
                    el('button', {
                        className: 'custom-dropdown-btn',
                        onClick: (e) => { e.stopPropagation(); toggleCustomDropdown('source-dropdown'); },
                    }, [
                        el('span', { className: 'dropdown-text', id: 'source-dropdown-text', textContent: '全部来源' }),
                        el('span', { className: 'dropdown-arrow', textContent: '▾' }),
                    ]),
                    el('div', { className: 'custom-dropdown-menu', id: 'source-dropdown-menu' }),
                ]),
            ]),
            el('div', { className: 'filter-group' }, [
                el('span', { className: 'filter-label', textContent: '时间' }),
                el('div', { className: 'custom-dropdown', id: 'time-dropdown' }, [
                    el('button', {
                        className: 'custom-dropdown-btn',
                        onClick: (e) => { e.stopPropagation(); toggleCustomDropdown('time-dropdown'); },
                    }, [
                        el('span', { className: 'dropdown-text', id: 'time-dropdown-text', textContent: '全部时间' }),
                        el('span', { className: 'dropdown-arrow', textContent: '▾' }),
                    ]),
                    el('div', { className: 'custom-dropdown-menu', id: 'time-dropdown-menu' }),
                ]),
            ]),
            el('div', { className: 'filter-group' }, [
                el('span', { className: 'filter-label', textContent: '每页' }),
                el('select', {
                    id: 'page-size-select',
                    className: 'filter-select',
                    value: String(state.pagination.perPage),
                    'data-action': 'per-page-change',
                }, [
                    el('option', { value: '20', textContent: '20' }),
                    el('option', { value: '50', textContent: '50' }),
                    el('option', { value: '100', textContent: '100' }),
                ]),
            ]),
            state.currentUser && state.currentUser.role === 'admin' ? el('div', { className: 'filter-group' }, [
                el('span', { className: 'filter-label', textContent: '归属' }),
                el('div', { className: 'custom-dropdown', id: 'owner-dropdown' }, [
                    el('button', {
                        className: 'custom-dropdown-btn',
                        onClick: (e) => { e.stopPropagation(); toggleCustomDropdown('owner-dropdown'); },
                    }, [
                        el('span', { className: 'dropdown-text', id: 'owner-dropdown-text', textContent: '全部归属' }),
                        el('span', { className: 'dropdown-arrow', textContent: '▾' }),
                    ]),
                    el('div', { className: 'custom-dropdown-menu', id: 'owner-dropdown-menu' }, [
                        el('div', { className: 'dropdown-search-wrap' }, [
                            el('input', {
                                id: 'owner-search-input',
                                className: 'dropdown-search-input',
                                type: 'text',
                                placeholder: '搜索用户...',
                                value: state.filters.ownerSearchKeyword || '',
                                onClick: (e) => e.stopPropagation(),
                                'data-action': 'owner-search-input',
                            }),
                        ]),
                        el('div', { id: 'owner-dropdown-items' }),
                    ]),
                ]),
            ]) : null,
        ]),
    ].filter(Boolean));

    slot.appendChild(filtersBar);

    if (!window._customDropdownListenerAdded) {
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.custom-dropdown')) {
                hideAllCustomDropdowns();
            }
        });
        window._customDropdownListenerAdded = true;
    }

    updateSourceDropdownOptions();
    updateTimeDropdownOptions();
    updateOwnerDropdownOptions();
}

function renderVideoGrid() {
    const gridSlot = $('#grid-slot');
    const countSlot = $('#count-slot');
    if (!gridSlot || !countSlot || state.nav.current !== 'media') return;

    gridSlot.innerHTML = '';
    countSlot.innerHTML = '';

    if (state.filteredVideos.length === 0) {
        const emptyState = el('div', { className: 'empty-state' }, [
            el('svg', { viewBox: '0 0 24 24', fill: 'currentColor' }, [
                el('path', { d: 'M4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6zm16-4H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H8V4h12v12z' }),
            ]),
            el('p', { textContent: '暂无媒体' }),
        ]);
        gridSlot.appendChild(emptyState);
        updateSelectAllCheckbox();
        return;
    }

    countSlot.appendChild(el('div', {
        className: 'admin-video-count',
        id: 'video-count',
        textContent: `共 ${state.pagination.total} 个媒体，当前第 ${state.pagination.page} 页，每页 ${state.pagination.perPage} 条`,
    }));

    const grid = el('div', { className: 'video-grid', id: 'video-grid' });
    state.filteredVideos.forEach(video => {
        grid.appendChild(renderVideoCard(video));
    });
    gridSlot.appendChild(grid);

    renderPagination();
    updateSelectAllCheckbox();
}

function renderVideoCard(video) {
    const isSelected = state.selectedVideos.has(video.filename);
    const hasThumbnail = video.thumbnail && video.thumbnail !== '';
    const durationLabel = formatDurationLabel(video.duration);

    const thumb = el('div', { className: 'video-thumb' }, [
        hasThumbnail
            ? el('img', { src: video.thumbnail, alt: video.title, loading: 'lazy' })
            : el('div', { className: 'empty-thumb', textContent: '无图' }),
        el('div', {
            className: 'video-duration-badge',
            textContent: durationLabel,
        }),
    ]);

    const info = el('div', { className: 'video-info' }, [
        el('div', {
            className: 'video-title',
            textContent: video.title || '未命名媒体',
            title: video.title,
        }),
        el('div', { className: 'video-summary-row' }, [
            el('div', { className: 'video-meta video-meta-primary' }, [
                el('span', { textContent: formatBytes(video.size) }),
                el('span', { textContent: new Date(video.created_at).toLocaleDateString('zh-CN') }),
            ]),
            el('div', { className: 'video-summary-badge-row' }, [
                el('span', { className: 'video-summary-badge', textContent: video.source || '未知来源' }),
                el('span', {
                    className: 'video-summary-badge',
                    textContent: video.is_legacy ? 'Legacy' : (video.owner_username || '未归属'),
                }),
            ]),
        ]),
        ((video.owner_count || 0) > 1 || (video.source_count || 0) > 1) ? el('div', { className: 'video-asset-stats' }, [
            (video.owner_count || 0) > 1 ? el('span', { textContent: `${video.owner_count || 0} 位拥有者` }) : null,
            (video.source_count || 0) > 1 ? el('span', { textContent: `${video.source_count || 0} 个来源` }) : null,
        ].filter(Boolean)) : null,
    ]);

    const selectToggle = el('button', {
        className: `video-select-toggle ${isSelected ? 'selected' : ''}`,
        textContent: isSelected ? '已选中' : '选择',
        title: isSelected ? '取消选择' : '选择媒体',
        'data-action': 'toggle-select',
        'data-filename': video.filename,
    });

    thumb.appendChild(selectToggle);

    const actionsBar = el('div', { className: 'video-actions-bar' }, [
        el('div', { className: 'action-group video-secondary-actions' }, [
            el('button', {
                className: 'action-btn',
                textContent: '详情',
                onClick: (e) => {
                    e.stopPropagation();
                    showMediaDetailsModal(video);
                },
            }),
            el('button', {
                className: 'action-btn share',
                textContent: '分享',
                ...(!video.share_token ? { disabled: true } : {}),
                onClick: (e) => {
                    e.stopPropagation();
                    if (!video.share_token) {
                        showToast('当前媒体未开启分享', 'warning');
                        return;
                    }
                    showShareModal(video);
                },
            }),
            el('button', {
                className: 'action-btn delete',
                textContent: '删除',
                onClick: (e) => {
                    e.stopPropagation();
                    handleDeleteVideo(video.filename);
                },
            }),
        ]),
    ]);

    const card = el('div', { className: 'video-card' }, [
        thumb,
        info,
        actionsBar,
    ]);

    card.addEventListener('click', (e) => {
        if (!e.target.closest('.action-btn') && !e.target.closest('.video-actions-bar') && !e.target.closest('.video-select-toggle')) {
            showPlayerModal(video);
        }
    });

    return card;
}

function renderPagination() {
    const slot = $('#pagination-slot');
    if (!slot || state.nav.current !== 'media') return;

    slot.innerHTML = '';
    const { page, totalPages } = state.pagination;

    if (totalPages <= 1) return;

    const pagination = el('div', { className: 'pagination', id: 'pagination' }, [
        el('button', {
            className: 'page-btn',
            textContent: '«',
            disabled: page === 1,
            onClick: () => goToPage(1),
        }),
        el('button', {
            className: 'page-btn',
            textContent: '‹',
            disabled: page === 1,
            onClick: () => goToPage(page - 1),
        }),
    ]);

    const maxButtons = 5;
    let startPage = Math.max(1, page - Math.floor(maxButtons / 2));
    let endPage = Math.min(totalPages, startPage + maxButtons - 1);
    if (endPage - startPage < maxButtons - 1) {
        startPage = Math.max(1, endPage - maxButtons + 1);
    }

    for (let i = startPage; i <= endPage; i++) {
        pagination.appendChild(el('button', {
            className: `page-btn ${i === page ? 'active' : ''}`,
            textContent: i,
            onClick: () => goToPage(i),
        }));
    }

    pagination.appendChild(el('span', { className: 'page-info', textContent: ` / ${totalPages}` }));

    pagination.appendChild(el('button', {
        className: 'page-btn',
        textContent: '›',
        disabled: page === totalPages,
        onClick: () => goToPage(page + 1),
    }));

    pagination.appendChild(el('button', {
        className: 'page-btn',
        textContent: '»',
        disabled: page === totalPages,
        onClick: () => goToPage(totalPages),
    }));

    slot.appendChild(pagination);
}

function renderBatchBar() {
    const existingBar = $('#batch-bar');
    if (existingBar) existingBar.remove();

    const bar = el('div', {
        className: 'batch-bar',
        id: 'batch-bar',
    }, [
        el('span', { className: 'batch-count', id: 'batch-count', textContent: '已选 0 个' }),
        el('button', {
            className: 'btn btn-secondary',
            textContent: '导出 ZIP',
            onClick: () => handleExportZip(),
        }),
        el('button', {
            className: 'btn btn-secondary',
            textContent: '导出 m3u8',
            onClick: () => handleExportM3u8(),
        }),
        el('button', {
            className: 'btn btn-danger',
            textContent: '批量删除',
            onClick: () => handleBatchDelete(),
        }),
        el('button', {
            className: 'btn btn-secondary',
            textContent: '取消选择',
            onClick: () => clearSelection(),
        }),
    ]);

    document.body.appendChild(bar);
}

function updateBatchBar() {
    const bar = $('#batch-bar');
    const count = $('#batch-count');
    const selectedCount = state.selectedVideos.size;

    if (!bar || !count) return;

    if (state.nav.current !== 'media') {
        bar.classList.remove('active');
        return;
    }

    if (selectedCount > 0) {
        bar.classList.add('active');
        count.textContent = `已选 ${selectedCount} 个`;
        bar.querySelectorAll('button').forEach(btn => {
            btn.disabled = false;
        });
    } else {
        bar.classList.remove('active');
    }
}

function _createDropdownItem(value, text, filterType) {
    return el('div', {
        className: 'custom-dropdown-item',
        'data-value': value,
        'data-action': 'filter-change',
        'data-filter-type': filterType,
    }, [document.createTextNode(text)]);
}

function toggleCustomDropdown(dropdownId) {
    const dropdown = $(`#${dropdownId}`);
    if (!dropdown) return;

    const menu = dropdown.querySelector('.custom-dropdown-menu');
    if (!menu) return;

    const isOpen = menu.classList.contains('show');
    hideAllCustomDropdowns();

    if (!isOpen) {
        menu.classList.add('show');
    }
}

function hideAllCustomDropdowns() {
    document.querySelectorAll('.custom-dropdown-menu.show').forEach(menu => {
        menu.classList.remove('show');
    });
}

function setCustomDropdownValue(dropdownId, value, text) {
    const dropdown = $(`#${dropdownId}`);
    if (!dropdown) return;

    const textEl = dropdown.querySelector('.dropdown-text');
    if (textEl) {
        textEl.textContent = text;
    }

    const menu = dropdown.querySelector('.custom-dropdown-menu');
    if (menu) {
        menu.querySelectorAll('.custom-dropdown-item').forEach(item => {
            item.classList.toggle('selected', item.getAttribute('data-value') === value);
        });
    }
}

function updateSourceDropdownOptions() {
    const menu = $('#source-dropdown-menu');
    if (!menu) return;

    menu.innerHTML = '';
    menu.appendChild(_createDropdownItem('', '全部', 'source'));

    state.allSources.forEach(source => {
        menu.appendChild(_createDropdownItem(source, source, 'source'));
    });

    const currentValue = state.filters.source || '';
    let currentText = '全部';
    menu.querySelectorAll('.custom-dropdown-item').forEach(item => {
        const selected = item.getAttribute('data-value') === currentValue;
        item.classList.toggle('selected', selected);
        if (selected) currentText = item.textContent;
    });

    const textEl = $('#source-dropdown-text');
    if (textEl) textEl.textContent = currentText;
}

function updateTimeDropdownOptions() {
    const menu = $('#time-dropdown-menu');
    if (!menu) return;

    menu.innerHTML = '';
    const timeOptions = [
        { value: 'all', text: '全部' },
        { value: 'today', text: '今天' },
        { value: 'week', text: '本周' },
        { value: 'month', text: '本月' },
        { value: 'earlier', text: '更早' },
    ];
    timeOptions.forEach(option => {
        menu.appendChild(_createDropdownItem(option.value, option.text, 'time'));
    });

    const currentValue = state.filters.time || 'all';
    let currentText = '全部';
    menu.querySelectorAll('.custom-dropdown-item').forEach(item => {
        const selected = item.getAttribute('data-value') === currentValue;
        item.classList.toggle('selected', selected);
        if (selected) currentText = item.textContent;
    });

    const textEl = $('#time-dropdown-text');
    if (textEl) textEl.textContent = currentText;
}

function updateOwnerDropdownOptions() {
    const itemsContainer = $('#owner-dropdown-items');
    if (!itemsContainer) return;

    itemsContainer.innerHTML = '';
    itemsContainer.appendChild(_createDropdownItem('all', '全部', 'owner'));
    itemsContainer.appendChild(_createDropdownItem('legacy', '未归属', 'owner'));

    const keyword = (state.filters.ownerSearchKeyword || '').trim().toLowerCase();
    const filteredUsers = state.users.filter(user => {
        if (!keyword) return true;
        return [
            String(user.username || '').toLowerCase(),
            String(user.display_name || '').toLowerCase(),
            String(user.id || ''),
        ].some((value) => value.includes(keyword));
    });

    filteredUsers.slice(0, 100).forEach(user => {
        itemsContainer.appendChild(_createDropdownItem(`user:${user.id}`, formatUserIdentityText(user), 'owner'));
    });

    if (filteredUsers.length === 0) {
        itemsContainer.appendChild(el('div', {
            className: 'custom-dropdown-empty',
            textContent: '没有匹配的用户',
        }));
    } else if (filteredUsers.length > 100) {
        itemsContainer.appendChild(el('div', {
            className: 'custom-dropdown-empty',
            textContent: `仅显示前 100 个匹配项，共 ${filteredUsers.length} 个`,
        }));
    }

    const currentValue = state.filters.owner || 'all';
    let currentText = '全部';
    itemsContainer.querySelectorAll('.custom-dropdown-item').forEach(item => {
        const selected = item.getAttribute('data-value') === currentValue;
        item.classList.toggle('selected', selected);
        if (selected) currentText = item.textContent;
    });

    const textEl = $('#owner-dropdown-text');
    if (textEl) textEl.textContent = currentText;
}

export { renderPage, renderNavbar, renderMainLayout, renderOverviewSection, renderSystemSection, renderStatsPanel, renderFilters, renderVideoGrid, renderVideoCard, renderPagination, renderBatchBar, updateBatchBar, ensureViewContainerVisible, toggleCustomDropdown, hideAllCustomDropdowns, setCustomDropdownValue, updateSourceDropdownOptions, updateTimeDropdownOptions, updateOwnerDropdownOptions };
