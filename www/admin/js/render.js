/**
 * GoTube Admin - 页面渲染模块
 * 导航栏、统计面板、筛选栏、视频网格、分页、批量操作栏
 */

/**
 * 渲染整个管理页面
 */
async function renderPage() {
    // 重置为视频视图
    state.currentView = 'videos';

    // 清空 body
    document.body.innerHTML = '';

    // 重新注入样式
    injectStyles();

    // 渲染导航栏（使用 window 确保使用全局函数）
    window.renderNavbar();

    // 渲染主内容区容器
    window.renderMainLayout();

    // 加载统计信息
    await window.loadStats();

    // 加载视频列表
    await window.loadVideos();

    // 渲染批量操作栏
    window.renderBatchBar();
    
    // 初始化点击外部区域返回视频管理的监听器
    if (typeof initClickOutsideListener === 'function') {
        initClickOutsideListener();
    }
}

/**
 * 渲染导航栏
 */
function renderNavbar() {
    const user = state.currentUser || { username: 'Unknown', role: 'user' };
    const isAdmin = user.role === 'admin';

    const navbar = el('nav', { className: 'navbar' }, [
        el('div', { className: 'nav-content' }, [
            el('a', {
                className: 'logo logo-link',
                textContent: '🎬 GoTube Admin',
                href: '#',
                title: '返回下载页',
                onClick: (e) => {
                    e.preventDefault();
                    const hiddenPath = window.GOTUBE_HIDDEN_PATH || '7777';
                    window.location.href = `/${hiddenPath}`;
                },
            }),
            el('div', { className: 'admin-actions' }, [
                el('div', { className: 'user-info-brief' }, [
                    el('span', { className: 'username', textContent: user.username }),
                    el('span', { className: `role-badge ${user.role}`, textContent: formatRole(user.role) }),
                ]),
                isAdmin ? el('button', {
                    className: 'btn btn-secondary',
                    textContent: '👥 用户管理',
                    onClick: () => window.showUserManagement(),
                }) : null,
                el('button', {
                    className: 'btn btn-secondary',
                    textContent: '📊 统计面板',
                    onClick: () => window.toggleStatsPanel(),
                }),
                el('div', { className: 'dropdown' }, [
                    el('button', {
                        className: 'btn btn-secondary',
                        textContent: '📤 导出 ▼',
                        id: 'export-btn',
                        onClick: () => window.toggleDropdown('export-menu'),
                    }),
                    el('div', { className: 'dropdown-menu', id: 'export-menu' }, [
                        el('div', {
                            className: 'dropdown-item',
                            textContent: '📦 导出 ZIP',
                            onClick: () => window.handleExportZip(),
                        }),
                        el('div', {
                            className: 'dropdown-item',
                            textContent: '📄 导出 JSON',
                            onClick: () => window.handleExportJson(),
                        }),
                        el('div', {
                            className: 'dropdown-item',
                            textContent: '🎵 导出 m3u8',
                            onClick: () => window.handleExportM3u8(),
                        }),
                    ]),
                ]),
                user.role !== 'readonly' ? el('button', {
                    className: 'btn btn-danger',
                    textContent: '🗑️ 批量删除',
                    id: 'batch-delete-btn',
                    disabled: true,
                    onClick: () => handleBatchDelete(),
                }) : null,
                el('button', {
                    className: 'btn btn-secondary',
                    textContent: '🍪 Cookie 管理',
                    onClick: () => window.showCookiesManagement(),
                }),
                el('button', {
                    className: 'btn btn-secondary',
                    textContent: '🚪 退出',
                    onClick: handleLogout,
                }),
            ]),
        ]),
    ]);

    document.body.appendChild(navbar);
}

/**
 * 渲染主布局容器（插槽）
 */
function renderMainLayout() {
    const main = el('div', { className: 'main', id: 'main-content' }, [
        // 视频视图容器
        el('div', { 
            id: 'video-view-container',
            style: 'display: block;' 
        }, [
            el('div', { id: 'stats-slot' }),
            el('div', { id: 'filters-slot' }),
            el('div', { id: 'count-slot', className: 'count-container' }),
            el('div', { id: 'grid-slot' }),
            el('div', { id: 'pagination-slot' }),
        ]),
        // 用户视图容器
        el('div', { 
            id: 'user-view-container',
            style: 'display: none;' 
        }, [
            el('div', { id: 'users-table-slot' }),
        ]),
    ]);
    document.body.appendChild(main);
}

/**
 * 渲染统计面板
 */
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

    // 总计卡片
    statsPanel.appendChild(el('div', { className: 'stat-card' }, [
        el('div', { className: 'stat-value', textContent: total }),
        el('div', { className: 'stat-label', textContent: '视频总数' }),
    ]));

    statsPanel.appendChild(el('div', { className: 'stat-card' }, [
        el('div', { className: 'stat-value', textContent: formatBytes(total_size) }),
        el('div', { className: 'stat-label', textContent: '总大小' }),
    ]));

    // 按来源统计
    if (sources && sources.length > 0) {
        const topSource = sources[0];
        statsPanel.appendChild(el('div', { className: 'stat-card' }, [
            el('div', { className: 'stat-value', textContent: topSource.name }),
            el('div', { className: 'stat-label', textContent: `${topSource.count} 个 (${topSource.percentage}%)` }),
        ]));
    }

    // 按时间统计 - 今天
    statsPanel.appendChild(el('div', { className: 'stat-card' }, [
        el('div', { className: 'stat-value', textContent: times.today || 0 }),
        el('div', { className: 'stat-label', textContent: '今天' }),
    ]));

    slot.appendChild(statsPanel);
}

/**
 * 切换统计面板显示/隐藏
 */
function toggleStatsPanel() {
    const panel = $('#stats-panel');
    if (panel) {
        panel.style.display = panel.style.display === 'none' ? 'grid' : 'none';
    } else {
        window.renderStatsPanel();
    }
}

/**
 * 渲染筛选栏
 */
function renderFilters() {
    const slot = $('#filters-slot');
    if (!slot || state.currentView !== 'videos') return;

    slot.innerHTML = '';

    const filtersBar = el('div', { className: 'filters', id: 'filters-bar' }, [
        // 全选/取消全选
        el('div', { className: 'filter-group' }, [
            el('input', {
                type: 'checkbox',
                id: 'select-all-checkbox',
                title: '全选/取消全选',
                checked: false,
                onChange: (e) => toggleSelectAll(e.target.checked),
            }),
            el('label', {
                for: 'select-all-checkbox',
                textContent: '全选',
                style: 'cursor: pointer; font-size: 13px; color: var(--text-sec);',
            }),
        ]),
        // 关键词搜索
        el('div', { className: 'filter-group' }, [
            el('span', { className: 'filter-label', textContent: '🔍' }),
            el('input', {
                className: 'search-input',
                id: 'search-input',
                type: 'text',
                placeholder: '按标题搜索...',
                value: state.filters.keyword,
                onInput: (e) => handleKeywordChange(e.target.value),
            }),
        ]),
        // 来源筛选（自定义下拉）
        el('div', { className: 'filter-group' }, [
            el('span', { className: 'filter-label', textContent: '来源:' }),
            el('div', { className: 'custom-dropdown', id: 'source-dropdown' }, [
                el('button', {
                    className: 'custom-dropdown-btn',
                    onClick: (e) => { e.stopPropagation(); window.toggleCustomDropdown('source-dropdown'); },
                }, [
                    el('span', { className: 'dropdown-text', id: 'source-dropdown-text', textContent: '全部' }),
                    el('span', { className: 'dropdown-arrow', textContent: '▼' }),
                ]),
                el('div', { className: 'custom-dropdown-menu', id: 'source-dropdown-menu' }),
            ]),
        ]),
        // 时间筛选（自定义下拉）
        el('div', { className: 'filter-group' }, [
            el('span', { className: 'filter-label', textContent: '时间:' }),
            el('div', { className: 'custom-dropdown', id: 'time-dropdown' }, [
                el('button', {
                    className: 'custom-dropdown-btn',
                    onClick: (e) => { e.stopPropagation(); window.toggleCustomDropdown('time-dropdown'); },
                }, [
                    el('span', { className: 'dropdown-text', id: 'time-dropdown-text', textContent: '全部' }),
                    el('span', { className: 'dropdown-arrow', textContent: '▼' }),
                ]),
                el('div', { className: 'custom-dropdown-menu', id: 'time-dropdown-menu' }),
            ]),
        ]),
    ]);

    slot.appendChild(filtersBar);

    // 初始化自定义下拉菜单点击外部关闭监听器
    if (!window._customDropdownListenerAdded) {
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.custom-dropdown')) {
                window.hideAllCustomDropdowns();
            }
        });
        window._customDropdownListenerAdded = true;
    }

    // 初始化下拉菜单选项
    window.updateSourceDropdownOptions();
    window.updateTimeDropdownOptions();
}

/**
 * 渲染视频网格
 */
function renderVideoGrid() {
    const gridSlot = $('#grid-slot');
    const countSlot = $('#count-slot');
    if (!gridSlot || !countSlot || state.currentView !== 'videos') return;

    gridSlot.innerHTML = '';
    countSlot.innerHTML = '';

    // 空状态检查
    if (state.filteredVideos.length === 0) {
        const emptyState = el('div', { className: 'empty-state' }, [
            el('svg', { viewBox: '0 0 24 24', fill: 'currentColor' }, [
                el('path', { d: 'M4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6zm16-4H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H8V4h12v12z' }),
            ]),
            el('p', { textContent: '暂无视频' }),
        ]);
        gridSlot.appendChild(emptyState);
        window.updateSelectAllCheckbox();
        return;
    }

    // 更新视频计数（显示在 count-slot，即网格上方）
    const countInfo = el('div', {
        className: 'admin-video-count',
        id: 'video-count',
        textContent: `共 ${state.pagination.total} 个视频，显示第 ${state.pagination.page} 页`,
    });
    countSlot.appendChild(countInfo);

    const grid = el('div', { className: 'video-grid', id: 'video-grid' });
    state.filteredVideos.forEach(video => {
        grid.appendChild(renderVideoCard(video));
    });
    gridSlot.appendChild(grid);

    // 渲染分页
    renderPagination();

    // 更新全选复选框状态
    window.updateSelectAllCheckbox();
}

/**
 * 渲染单个视频卡片
 */
function renderVideoCard(video) {
    const isSelected = state.selectedVideos.has(video.filename);
    const hasThumbnail = video.thumbnail && video.thumbnail !== '';

    // 缩略图区域
    const thumb = el('div', { className: 'video-thumb' }, [
        hasThumbnail
            ? el('img', { src: video.thumbnail, alt: video.title, loading: 'lazy' })
            : el('div', { className: 'empty-thumb', textContent: '🎬' }),
    ]);

    // 信息区域
    const info = el('div', { className: 'video-info' }, [
        el('div', {
            className: 'video-title',
            textContent: video.title || '未命名视频',
            title: video.title,
        }),
        el('div', { className: 'video-meta' }, [
            el('span', { textContent: formatBytes(video.size) }),
            el('span', { textContent: new Date(video.created_at).toLocaleDateString('zh-CN') }),
        ]),
        el('div', {
            className: 'video-source',
            textContent: video.source || 'Unknown',
        }),
    ]);

    // 复选框（作为操作按钮样式）
    const checkbox = el('button', {
        className: `action-btn select-btn ${isSelected ? 'selected' : ''}`,
        textContent: isSelected ? '☑' : '☐',
        title: isSelected ? '取消选择' : '选择此视频',
        onClick: (e) => {
            e.stopPropagation();
            // 直接从 state 中读取当前选中状态，而不是使用闭包变量
            const isCurrentlySelected = state.selectedVideos.has(video.filename);
            const newState = !isCurrentlySelected;
            toggleVideoSelection(video.filename, newState);
            // 更新当前按钮状态
            checkbox.textContent = newState ? '☑' : '☐';
            checkbox.classList.toggle('selected', newState);
            // 同步全选框状态
            window.updateSelectAllCheckbox();
        },
    });

    // 操作栏（左边是分享/删除/选择按钮）
    const actionsBar = el('div', { className: 'video-actions-bar' }, [
        el('div', { className: 'action-group' }, [
            el('button', {
                className: 'action-btn share',
                textContent: '🔗 分享',
                onClick: (e) => {
                    e.stopPropagation();
                    window.showShareModal(video);
                },
            }),
            state.currentUser && state.currentUser.role !== 'readonly' ? el('button', {
                className: 'action-btn delete',
                textContent: '🗑️ 删除',
                onClick: (e) => {
                    e.stopPropagation();
                    window.handleDeleteVideo(video.filename);
                },
            }) : null,
        ]),
        // 选择按钮放在最右边
        el('div', { className: 'action-group' }, [
            checkbox,
        ]),
    ]);

    // 组合卡片
    const card = el('div', { className: 'video-card' }, [
        thumb,
        info,
        actionsBar,
    ]);

    // 点击整个卡片播放（排除按钮和复选框）
    card.addEventListener('click', (e) => {
        if (!e.target.closest('.action-btn') && !e.target.closest('.video-actions-bar')) {
            window.showPlayerModal(video);
        }
    });

    return card;
}

/**
 * 渲染分页
 */
function renderPagination() {
    const slot = $('#pagination-slot');
    if (!slot || state.currentView !== 'videos') return;

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

    // 计算显示的页码范围
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

/**
 * 渲染批量操作栏
 */
function renderBatchBar() {
    if (state.currentView !== 'videos') return;

    // 移除已有的批量操作栏
    const existingBar = $('#batch-bar');
    if (existingBar) existingBar.remove();

    const bar = el('div', {
        className: 'batch-bar',
        id: 'batch-bar',
    }, [
        el('span', { className: 'batch-count', id: 'batch-count', textContent: '已选 0 个' }),
        el('button', {
            className: 'btn btn-secondary',
            textContent: '📦 导出 ZIP',
            onClick: () => window.handleExportZip(),
        }),
        el('button', {
            className: 'btn btn-secondary',
            textContent: '🎵 导出 m3u8',
            onClick: () => window.handleExportM3u8(),
        }),
        state.currentUser && state.currentUser.role !== 'readonly' ? el('button', {
            className: 'btn btn-danger',
            textContent: '🗑️ 批量删除',
            onClick: () => window.handleBatchDelete(),
        }) : null,
        el('button', {
            className: 'btn btn-secondary',
            textContent: '取消选择',
            onClick: () => window.clearSelection(),
        }),
    ]);

    document.body.appendChild(bar);
}

/**
 * 更新批量操作栏状态
 */
function updateBatchBar() {
    if (state.currentView !== 'videos') return;

    const bar = $('#batch-bar');
    const count = $('#batch-count');
    const deleteBtnNav = $('#batch-delete-btn'); // 导航栏的删除按钮
    const buttons = bar ? bar.querySelectorAll('button') : [];

    const selectedCount = state.selectedVideos.size;

    if (selectedCount > 0) {
        // 显示批量操作栏
        if (bar) bar.classList.add('active');
        if (count) count.textContent = `已选 ${selectedCount} 个`;
        
        // 启用所有按钮（导航栏和批量操作栏的删除按钮）
        if (deleteBtnNav) deleteBtnNav.disabled = false;
        buttons.forEach(btn => {
            btn.disabled = false;
        });
    } else {
        // 隐藏批量操作栏
        if (bar) bar.classList.remove('active');
        
        // 禁用导航栏的删除按钮
        if (deleteBtnNav) deleteBtnNav.disabled = true;
    }
}

// 显式挂载到 window，确保全局可见性
window.renderPage = renderPage;
window.renderNavbar = renderNavbar;
window.renderMainLayout = renderMainLayout;
window.renderStatsPanel = renderStatsPanel;
window.toggleStatsPanel = toggleStatsPanel;
window.renderFilters = renderFilters;
window.renderVideoGrid = renderVideoGrid;
window.renderVideoCard = renderVideoCard;
window.renderPagination = renderPagination;
window.renderBatchBar = renderBatchBar;
window.updateBatchBar = updateBatchBar;

// ========== 自定义下拉菜单辅助函数 ==========

/**
 * 创建下拉菜单项
 */
function _createDropdownItem(value, text, filterType) {
    return el('div', {
        className: 'custom-dropdown-item',
        'data-value': value,
        onClick: (e) => {
            e.stopPropagation();
            if (filterType === 'source') {
                handleSourceChange(value);
                window.setCustomDropdownValue('source-dropdown', value, text);
            } else if (filterType === 'time') {
                handleTimeChange(value);
                window.setCustomDropdownValue('time-dropdown', value, text);
            }
            window.hideAllCustomDropdowns();
        },
    }, [document.createTextNode(text)]);
}

/**
 * 切换自定义下拉菜单显示/隐藏
 */
function toggleCustomDropdown(dropdownId) {
    const dropdown = $(`#${dropdownId}`);
    if (!dropdown) return;

    const menu = dropdown.querySelector('.custom-dropdown-menu');
    if (!menu) return;

    const isOpen = menu.classList.contains('show');

    // 先关闭所有菜单
    hideAllCustomDropdowns();

    // 如果原来是关闭的，现在打开它
    if (!isOpen) {
        menu.classList.add('show');
    }
}

/**
 * 隐藏所有自定义下拉菜单
 */
function hideAllCustomDropdowns() {
    document.querySelectorAll('.custom-dropdown-menu.show').forEach(menu => {
        menu.classList.remove('show');
    });
}

/**
 * 设置自定义下拉菜单的选中值
 */
function setCustomDropdownValue(dropdownId, value, text) {
    const dropdown = $(`#${dropdownId}`);
    if (!dropdown) return;

    const textEl = dropdown.querySelector('.dropdown-text');
    if (textEl) {
        textEl.textContent = text;
    }

    // 更新选中项样式
    const menu = dropdown.querySelector('.custom-dropdown-menu');
    if (menu) {
        menu.querySelectorAll('.custom-dropdown-item').forEach(item => {
            if (item.getAttribute('data-value') === value) {
                item.classList.add('selected');
            } else {
                item.classList.remove('selected');
            }
        });
    }
}

/**
 * 更新来源下拉菜单选项
 */
function updateSourceDropdownOptions() {
    const menu = $('#source-dropdown-menu');
    if (!menu) return;

    // 清空并重建选项
    menu.innerHTML = '';
    menu.appendChild(_createDropdownItem('', '全部', 'source'));

    state.allSources.forEach(s => {
        menu.appendChild(_createDropdownItem(s, s, 'source'));
    });

    // 设置当前选中项
    const currentValue = state.filters.source || '';
    let currentText = '全部';
    menu.querySelectorAll('.custom-dropdown-item').forEach(item => {
        if (item.getAttribute('data-value') === currentValue) {
            item.classList.add('selected');
            currentText = item.textContent;
        } else {
            item.classList.remove('selected');
        }
    });

    // 更新按钮显示文本
    const textEl = $('#source-dropdown-text');
    if (textEl) {
        textEl.textContent = currentText;
    }
}

/**
 * 更新时间下拉菜单选项
 */
function updateTimeDropdownOptions() {
    const menu = $('#time-dropdown-menu');
    if (!menu) return;

    // 清空并重建选项
    menu.innerHTML = '';
    const timeOptions = [
        { value: 'all', text: '全部' },
        { value: 'today', text: '今天' },
        { value: 'week', text: '本周' },
        { value: 'month', text: '本月' },
        { value: 'earlier', text: '更早' },
    ];
    timeOptions.forEach(opt => {
        menu.appendChild(_createDropdownItem(opt.value, opt.text, 'time'));
    });

    // 设置当前选中项
    const currentValue = state.filters.time || 'all';
    let currentText = '全部';
    menu.querySelectorAll('.custom-dropdown-item').forEach(item => {
        if (item.getAttribute('data-value') === currentValue) {
            item.classList.add('selected');
            currentText = item.textContent;
        } else {
            item.classList.remove('selected');
        }
    });

    // 更新按钮显示文本
    const textEl = $('#time-dropdown-text');
    if (textEl) {
        textEl.textContent = currentText;
    }
}

// 挂载自定义下拉菜单函数到 window
window.toggleCustomDropdown = toggleCustomDropdown;
window.hideAllCustomDropdowns = hideAllCustomDropdowns;
window.setCustomDropdownValue = setCustomDropdownValue;
window.updateSourceDropdownOptions = updateSourceDropdownOptions;
window.updateTimeDropdownOptions = updateTimeDropdownOptions;
