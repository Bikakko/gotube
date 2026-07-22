/**
 * GoTube Admin - user management module
 * Load users, edit profiles, toggle status, and inspect user libraries.
 */

function refreshNavTabs() {
    document.querySelectorAll('[data-admin-nav]').forEach((btn) => {
        btn.classList.toggle('active', btn.dataset.adminNav === state.nav.current);
    });
}

function switchAdminView(view) {
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
        container.classList.toggle('view-active', active);
        if (active) {
            container.classList.remove('view-active');
            requestAnimationFrame(() => {
                container.classList.add('view-active');
            });
        }
    });

    state.nav.current = view;
    state.isTransitioning = false;
    window.renderNavbar();
    refreshNavTabs();

    if (view === 'media') {
        window.updateBatchBar();
    } else {
        const bar = $('#batch-bar');
        if (bar) bar.classList.remove('active');
    }
}

async function showUserManagement() {
    if (state.currentUser && state.currentUser.role !== 'admin') {
        showToast('\u6743\u9650\u4e0d\u8db3', 'error');
        return;
    }

    document.title = 'GoTube Admin - \u7528\u6237';
    switchAdminView('users');
    await loadUsers(state.usersLoaded);
}

async function showVideoManagement() {
    document.title = 'GoTube Admin - \u5168\u5c40\u5a92\u4f53';
    switchAdminView('media');
    await window.loadStats();
    await window.loadVideos();
}

window._clickOutsideListenerInitialized = false;

function initClickOutsideListener() {
    return;
}

async function loadUsers(forceReload = false) {
    if (state.usersLoaded && !forceReload && state.users.length > 0) {
        renderUsersTable(filterUsers(state.users));
        return;
    }

    const slot = $('#users-table-slot');
    if (slot) {
        slot.innerHTML = '<div class="loading">\u52a0\u8f7d\u4e2d</div>';
    }

    try {
        const users = await apiFetch('/users');
        state.users = users;
        state.usersLoaded = true;
        renderUsersTable(filterUsers(users));
    } catch (err) {
        console.error('\u52a0\u8f7d\u7528\u6237\u5217\u8868\u5931\u8d25:', err);
        if (slot) {
            slot.innerHTML = `<div class="error">\u52a0\u8f7d\u5931\u8d25: ${err.message}</div>`;
        }
    }
}

function getUserSearchKeyword() {
    return String(state.userSearchKeyword || '').trim().toLowerCase();
}

function getUserStatusFilter() {
    return String(state.userStatusFilter || 'all');
}

function getUserRoleFilter() {
    return String(state.userRoleFilter || 'all');
}

function filterUsers(users) {
    const keyword = getUserSearchKeyword();
    const statusFilter = getUserStatusFilter();
    const roleFilter = getUserRoleFilter();

    const filtered = users.filter((user) => {
        if (statusFilter === 'active' && !user.is_active) return false;
        if (statusFilter === 'inactive' && user.is_active) return false;
        if (roleFilter !== 'all' && String(user.role || 'user') !== roleFilter) return false;

        if (!keyword) return true;

        const username = String(user.username || '').toLowerCase();
        const displayName = String(user.display_name || '').toLowerCase();
        const idText = String(user.id || '');
        const roleText = String(user.role || '').toLowerCase();
        const statusText = user.is_active ? '\u542f\u7528 active' : '\u7981\u7528 inactive';

        if (/^\d+$/.test(keyword)) {
            return idText === keyword || username.includes(keyword) || displayName.includes(keyword);
        }
        return [username, displayName, idText, roleText, statusText].some((value) => value.includes(keyword));
    });

    if (!keyword || !/^\d+$/.test(keyword)) {
        return filtered;
    }

    return filtered.slice().sort((a, b) => {
        const aExact = String(a.id || '') === keyword ? 0 : 1;
        const bExact = String(b.id || '') === keyword ? 0 : 1;
        if (aExact !== bExact) return aExact - bExact;
        return String(a.username || '').localeCompare(String(b.username || ''), 'zh-CN');
    });
}

function rerenderUsersTablePreservingSearch() {
    const active = document.activeElement;
    const hadFocus = active && active.id === 'user-search-input';
    const selectionStart = hadFocus && typeof active.selectionStart === 'number' ? active.selectionStart : null;
    const selectionEnd = hadFocus && typeof active.selectionEnd === 'number' ? active.selectionEnd : null;

    renderUsersTable(filterUsers(state.users));

    if (!hadFocus) return;

    const nextInput = $('#user-search-input');
    if (!nextInput) return;

    nextInput.focus();
    if (selectionStart !== null && selectionEnd !== null) {
        nextInput.setSelectionRange(selectionStart, selectionEnd);
    }
}

function renderUsersTable(users) {
    const slot = $('#users-table-slot');
    if (!slot) return;

    const container = el('div', { className: 'user-management-shell' });
    container.appendChild(el('div', { className: 'admin-section-header' }, [
        el('div', {}, [
            el('h2', { textContent: '\u7528\u6237' }),
        ]),
        el('button', {
            className: 'btn btn-primary',
            textContent: '\u65b0\u589e\u7528\u6237',
            onClick: () => showUserEditModal(),
        }),
    ]));

    container.appendChild(el('div', { className: 'user-toolbar' }, [
        el('div', { className: 'user-toolbar-main' }, [
            el('input', {
                id: 'user-search-input',
                className: 'search-input user-search-input',
                type: 'search',
                placeholder: '\u8f93\u5165\u8d26\u53f7\u3001\u6635\u79f0\u6216\u7528\u6237 ID',
                value: state.userSearchKeyword || '',
            }),
            el('select', {
                id: 'user-status-filter',
                className: 'filter-select user-filter-select',
            }, [
                el('option', { value: 'all', textContent: '\u5168\u90e8\u72b6\u6001' }),
                el('option', { value: 'active', textContent: '\u542f\u7528' }),
                el('option', { value: 'inactive', textContent: '\u7981\u7528' }),
            ]),
            el('select', {
                id: 'user-role-filter',
                className: 'filter-select user-filter-select',
            }, [
                el('option', { value: 'all', textContent: '\u5168\u90e8\u89d2\u8272' }),
                el('option', { value: 'admin', textContent: '\u7ba1\u7406\u5458' }),
                el('option', { value: 'user', textContent: '\u666e\u901a\u7528\u6237' }),
            ]),
        ]),
        el('div', {
            className: 'user-search-summary user-summary-pill',
            textContent: `\u663e\u793a ${users.length} / ${state.users.length} \u4e2a\u7528\u6237`,
        }),
    ]));

    const searchInput = container.querySelector('#user-search-input');
    if (searchInput) {
        searchInput.addEventListener('input', (event) => {
            state.userSearchKeyword = event.target.value;
            rerenderUsersTablePreservingSearch();
        });
    }

    const statusFilter = container.querySelector('#user-status-filter');
    if (statusFilter) {
        statusFilter.value = getUserStatusFilter();
        statusFilter.addEventListener('change', (event) => {
            state.userStatusFilter = event.target.value;
            renderUsersTable(filterUsers(state.users));
        });
    }

    const roleFilter = container.querySelector('#user-role-filter');
    if (roleFilter) {
        roleFilter.value = getUserRoleFilter();
        roleFilter.addEventListener('change', (event) => {
            state.userRoleFilter = event.target.value;
            renderUsersTable(filterUsers(state.users));
        });
    }

    if (users.length === 0) {
        slot.innerHTML = '';
        container.appendChild(el('div', { className: 'empty-state empty-state-card', textContent: '\u6ca1\u6709\u5339\u914d\u7684\u7528\u6237' }));
        slot.appendChild(container);
        return;
    }

    const table = el('table', { className: 'users-table users-table-fixed users-table-users-v2' }, [
        el('colgroup', {}, [
            el('col', { className: 'users-col-id' }),
            el('col', { className: 'users-col-identity' }),
            el('col', { className: 'users-col-status' }),
            el('col', { className: 'users-col-video-count' }),
            el('col', { className: 'users-col-capacity' }),
            el('col', { className: 'users-col-last-login' }),
            el('col', { className: 'users-col-actions' }),
        ]),
        el('thead', {}, [
            el('tr', {}, [
                el('th', { textContent: 'ID' }),
                el('th', { textContent: '\u7528\u6237' }),
                el('th', { textContent: '\u72b6\u6001' }),
                el('th', { textContent: '\u89c6\u9891\u6570' }),
                el('th', { textContent: '\u5bb9\u91cf' }),
                el('th', { textContent: '\u6700\u540e\u767b\u5f55' }),
                el('th', { textContent: '\u64cd\u4f5c' }),
            ]),
        ]),
        el('tbody', {}, users.map((user) => {
            const isSelf = state.currentUser && state.currentUser.id === user.id;
            const isSystemAccount = user.is_system_account || user.role === 'admin';
            const accountNote = isSystemAccount
                ? '\u7cfb\u7edf\u8d26\u53f7'
                : (isSelf ? '\u5f53\u524d\u767b\u5f55\u7528\u6237' : '');

            return el('tr', { className: user.is_active ? '' : 'inactive' }, [
                el('td', { className: 'user-id-cell', textContent: user.id }),
                el('td', { className: 'user-identity-cell' }, [
                    el('div', { className: `user-identity-card ${(user.role || 'user')}` }, [
                        el('div', {
                            className: 'user-name-main',
                            textContent: `\u6635\u79f0\uff1a${user.display_name || user.username}`,
                        }),
                        el('div', {
                            className: 'user-name-sub',
                            textContent: `\u8d26\u53f7\uff1a${user.username}`,
                        }),
                        el('div', { className: 'user-identity-meta' }, [
                            el('span', {
                                className: `role-badge ${user.role || 'user'}`,
                                textContent: formatRole(user.role),
                            }),
                            accountNote ? el('span', {
                                className: 'user-note-badge',
                                textContent: accountNote,
                            }) : null,
                        ].filter(Boolean)),
                    ]),
                ]),
                el('td', { className: 'user-status-cell' }, [
                    el('span', {
                        className: `status-badge ${user.is_active ? 'active' : 'inactive'}`,
                        textContent: user.is_active ? '\u542f\u7528' : '\u7981\u7528',
                    }),
                ]),
                el('td', { className: 'user-count-cell', textContent: String(user.video_count || 0) }),
                el('td', { className: 'user-capacity-cell' }, [
                    el('span', {
                        className: 'user-capacity-value',
                        textContent: user.role === 'admin'
                            ? '\u4e0d\u9650'
                            : `${formatBytes(user.storage_used_bytes || 0)} / ${formatUserQuota(user.storage_quota_mb)}`,
                    }),
                ]),
                el('td', {
                    className: 'user-last-login-cell',
                    textContent: user.last_login
                        ? new Date(user.last_login).toLocaleString('zh-CN')
                        : '\u4ece\u672a\u767b\u5f55',
                }),
                el('td', { className: 'user-actions user-actions-compact' }, [
                    el('button', {
                        className: 'action-btn-sm',
                        textContent: '\u89c6\u9891\u5e93',
                        onClick: (e) => {
                            e.stopPropagation();
                            showUserLibraryModal(user);
                        },
                    }),
                    el('button', {
                        className: 'action-btn-sm',
                        textContent: '\u7f16\u8f91',
                        onClick: (e) => {
                            e.stopPropagation();
                            showUserEditModal(user);
                        },
                    }),
                    isSystemAccount ? null : el('button', {
                        className: 'action-btn-sm',
                        textContent: '\u5bc6\u7801',
                        onClick: (e) => {
                            e.stopPropagation();
                            showChangePasswordModal(user);
                        },
                    }),
                    !isSelf && !isSystemAccount ? el('button', {
                        className: `action-btn-sm ${user.is_active ? 'danger' : 'success'}`,
                        textContent: user.is_active ? '\u7981\u7528' : '\u542f\u7528',
                        onClick: (e) => {
                            e.stopPropagation();
                            toggleUserActive(user);
                        },
                    }) : null,
                    !isSelf && !isSystemAccount ? el('button', {
                        className: 'action-btn-sm danger',
                        textContent: '\u5220\u9664',
                        onClick: (e) => {
                            e.stopPropagation();
                            handleDeleteUser(user);
                        },
                    }) : null,
                ].filter(Boolean)),
            ]);
        })),
    ]);

    slot.innerHTML = '';
    container.appendChild(el('div', { className: 'users-table-shell' }, [table]));
    slot.appendChild(container);
}

async function showUserLibraryModal(user) {
    state.userLibrary.user = user;
    state.userLibrary.items = [];
    state.userLibrary.loading = true;

    const overlay = el('div', { className: 'modal active', id: 'user-library-modal' }, [
        el('div', { className: 'modal-content' }, [
            el('div', { className: 'modal-header' }, [
                el('div', {
                    className: 'modal-title',
                    textContent: `\u8d26\u53f7\uff1a${user.username} | \u6635\u79f0\uff1a${user.display_name || user.username} | ID\uff1a${user.id} \u7684\u89c6\u9891\u5e93`,
                }),
                el('button', {
                    className: 'modal-close',
                    textContent: '\u00d7',
                    onClick: () => closeModal('user-library-modal'),
                }),
            ]),
            el('div', { className: 'modal-body', id: 'user-library-body' }, [
                el('div', { className: 'loading', textContent: '\u52a0\u8f7d\u4e2d' }),
            ]),
        ]),
    ]);

    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
            closeModal('user-library-modal');
        }
    });

    document.body.appendChild(overlay);
    await fetchUserLibraryAndRender(user.id);
}

async function fetchUserLibraryAndRender(userId) {
    try {
        const data = await window.loadUserLibrary(userId);
        state.userLibrary.user = data.user;
        state.userLibrary.items = data.items || [];
        state.userLibrary.loading = false;
        renderUserLibraryModal();
    } catch (err) {
        state.userLibrary.loading = false;
        const body = $('#user-library-body');
        if (body) {
            body.innerHTML = `<div class="error">\u52a0\u8f7d\u5931\u8d25: ${err.message}</div>`;
        }
    }
}

function renderUserLibraryModal() {
    const body = $('#user-library-body');
    if (!body) return;

    const items = state.userLibrary.items || [];
    body.innerHTML = '';

    if (items.length === 0) {
        body.appendChild(el('div', { className: 'empty-state empty-state-card', textContent: '\u8be5\u7528\u6237\u6682\u65e0\u89c6\u9891' }));
        return;
    }

    const list = el('div', { className: 'user-library-list' });
    items.forEach((item) => {
        list.appendChild(el('article', { className: 'user-library-item' }, [
            el('div', { className: 'user-library-thumb' }, [
                item.thumbnail_url
                    ? el('img', { src: item.thumbnail_url, alt: item.title, loading: 'lazy' })
                    : el('div', { className: 'preview-thumb-empty', textContent: '\ud83c\udf9e' }),
            ]),
            el('div', { className: 'user-library-main' }, [
                el('div', { className: 'preview-title', textContent: item.title || '\u672a\u547d\u540d\u89c6\u9891' }),
                el('div', { className: 'user-library-meta' }, [
                    el('span', { textContent: formatBytes(item.size || 0) }),
                    el('span', { textContent: item.source || '\u672a\u77e5\u6765\u6e90' }),
                    el('span', {
                        textContent: item.saved_at
                            ? new Date(item.saved_at).toLocaleString('zh-CN')
                            : '\u65e0\u4fdd\u5b58\u65f6\u95f4',
                    }),
                ]),
                el('div', { className: 'video-asset-stats' }, [
                    el('span', { textContent: item.share_enabled ? '\u5206\u4eab\u5df2\u5f00\u542f' : '\u5206\u4eab\u672a\u5f00\u542f' }),
                ]),
            ]),
            el('div', { className: 'user-library-actions' }, [
                el('button', {
                    className: 'action-btn',
                    textContent: '\u64ad\u653e',
                    onClick: () => window.showPlayerModal(item),
                }),
                el('button', {
                    className: 'action-btn share',
                    textContent: '\u5206\u4eab',
                    ...(!item.share_token ? { disabled: true } : {}),
                    onClick: () => window.showShareModal(item),
                }),
            ]),
        ]));
    });

    body.appendChild(list);
}

function formatRole(role) {
    const map = {
        admin: '\u7ba1\u7406\u5458',
        user: '\u666e\u901a\u7528\u6237',
    };
    return map[role] || role;
}

function formatUserQuota(quotaMb) {
    if (quotaMb === 0) return '\u4e0d\u9650';
    if (quotaMb === null || quotaMb === undefined) return '\u9ed8\u8ba4';
    return `${quotaMb} MB`;
}

async function toggleUserActive(user) {
    try {
        await apiFetch(`/users/${user.id}`, {
            method: 'PUT',
            body: JSON.stringify({ is_active: !user.is_active }),
        });
        showToast(`\u7528\u6237\u5df2${user.is_active ? '\u7981\u7528' : '\u542f\u7528'}`, 'success');
        invalidateUserCache();
        await loadUsers(true);
    } catch (err) {
        showToast('\u64cd\u4f5c\u5931\u8d25: ' + err.message, 'error');
    }
}

async function handleDeleteUser(user) {
    if (!confirm(`\u786e\u5b9a\u8981\u5220\u9664\u7528\u6237\u201c${user.username}\u201d\u5417\uff1f\u6b64\u64cd\u4f5c\u4e0d\u53ef\u6062\u590d\u3002`)) return;

    try {
        await apiFetch(`/users/${user.id}`, { method: 'DELETE' });
        showToast('\u7528\u6237\u5df2\u5220\u9664', 'success');
        invalidateUserCache();
        await loadUsers(true);
    } catch (err) {
        showToast('\u5220\u9664\u5931\u8d25: ' + err.message, 'error');
    }
}

function showUserEditModal(user = null) {
    const isEdit = !!user;
    const title = isEdit ? '\u7f16\u8f91\u7528\u6237' : '\u65b0\u589e\u7528\u6237';
    const isAdminAccount = Boolean(user && (user.is_system_account || user.role === 'admin'));

    const overlay = el('div', { className: 'modal active', id: 'user-edit-modal' }, [
        el('div', { className: 'modal-content modal-sm' }, [
            el('div', { className: 'modal-header' }, [
                el('div', { className: 'modal-title', textContent: title }),
                el('button', {
                    className: 'modal-close',
                    textContent: '\u00d7',
                    onClick: () => closeModal('user-edit-modal'),
                }),
            ]),
            el('div', { className: 'modal-body' }, [
                el('div', { className: 'form-group' }, [
                    el('label', { textContent: '\u8d26\u53f7' }),
                    el('input', {
                        type: 'text',
                        id: 'edit-username',
                        value: user ? user.username : '',
                        placeholder: '\u8bf7\u8f93\u5165\u8d26\u53f7',
                        ...(isEdit ? { disabled: true } : {}),
                    }),
                ]),
                el('div', { className: 'form-group' }, [
                    el('label', { textContent: '\u6635\u79f0' }),
                    el('input', {
                        type: 'text',
                        id: 'edit-display-name',
                        value: user ? (user.display_name || user.username) : '',
                        placeholder: '\u8bf7\u8f93\u5165\u6635\u79f0',
                    }),
                ]),
                !isEdit ? el('div', { className: 'form-group' }, [
                    el('label', { textContent: '\u5bc6\u7801' }),
                    el('input', {
                        type: 'password',
                        id: 'edit-password',
                        placeholder: '\u8bf7\u8f93\u5165\u5bc6\u7801',
                    }),
                ]) : null,
                isAdminAccount ? null : el('div', { className: 'form-group' }, [
                    el('label', { textContent: '\u89d2\u8272' }),
                    el('select', { id: 'edit-role' }, [
                        el('option', {
                            value: 'user',
                            textContent: '\u666e\u901a\u7528\u6237',
                            selected: user ? user.role === 'user' : true,
                        }),
                    ]),
                ]),
                !isAdminAccount ? el('div', { className: 'form-group' }, [
                    el('label', { textContent: '\u89c6\u9891\u5e93\u5bb9\u91cf MB' }),
                    el('input', {
                        type: 'number',
                        id: 'edit-storage-quota',
                        min: '0',
                        value: user && user.storage_quota_mb !== null && user.storage_quota_mb !== undefined
                            ? String(user.storage_quota_mb)
                            : '',
                        placeholder: '\u7559\u7a7a\u4f7f\u7528\u9ed8\u8ba4\u503c\uff0c0 \u8868\u793a\u4e0d\u9650',
                    }),
                ]) : null,
            ].filter(Boolean)),
            el('div', { className: 'modal-footer' }, [
                el('button', {
                    className: 'btn btn-secondary',
                    textContent: '\u53d6\u6d88',
                    onClick: () => closeModal('user-edit-modal'),
                }),
                el('button', {
                    className: 'btn btn-primary',
                    textContent: '\u4fdd\u5b58',
                    onClick: () => handleSaveUser(user),
                }),
            ]),
        ]),
    ]);

    document.body.appendChild(overlay);
}

async function handleSaveUser(user) {
    const isEdit = !!user;
    const username = $('#edit-username').value.trim();
    const displayName = $('#edit-display-name').value.trim();
    const roleEl = $('#edit-role');
    const role = roleEl ? roleEl.value : (user ? user.role : 'user');
    const quotaInput = $('#edit-storage-quota');
    const quotaRaw = quotaInput ? quotaInput.value.trim() : '';

    if (!username) {
        showToast('\u8bf7\u8f93\u5165\u8d26\u53f7', 'warning');
        return;
    }
    if (!displayName) {
        showToast('\u8bf7\u8f93\u5165\u6635\u79f0', 'warning');
        return;
    }

    try {
        if (isEdit) {
            const payload = { username, display_name: displayName, role };
            if (quotaInput) {
                if (quotaRaw === '') {
                    payload.storage_quota_mb = null;
                } else {
                    const quotaMb = Number.parseInt(quotaRaw, 10);
                    if (!Number.isInteger(quotaMb) || quotaMb < 0) {
                        showToast('\u5bb9\u91cf\u5fc5\u987b\u4e3a\u7a7a\u3001 0 \u6216\u6b63\u6574\u6570', 'warning');
                        return;
                    }
                    payload.storage_quota_mb = quotaMb;
                }
            }

            await apiFetch(`/users/${user.id}`, {
                method: 'PUT',
                body: JSON.stringify(payload),
            });
            showToast('\u66f4\u65b0\u6210\u529f', 'success');
            closeModal('user-edit-modal');
        } else {
            const password = $('#edit-password').value;
            if (!password) {
                showToast('\u8bf7\u8f93\u5165\u5bc6\u7801', 'warning');
                return;
            }
            await apiFetch('/users', {
                method: 'POST',
                body: JSON.stringify({ username, display_name: displayName, password, role }),
            });
            showToast('\u521b\u5efa\u6210\u529f', 'success');
            closeModal('user-edit-modal');
        }

        invalidateUserCache();
        await loadUsers(true);
    } catch (err) {
        showToast(err.message || '\u64cd\u4f5c\u5931\u8d25', 'error');
    }
}

function showChangePasswordModal(user) {
    const isSelf = state.currentUser && state.currentUser.id === user.id;

    const overlay = el('div', { className: 'modal active', id: 'password-modal' }, [
        el('div', { className: 'modal-content modal-sm' }, [
            el('div', { className: 'modal-header' }, [
                el('div', { className: 'modal-title', textContent: `\u4fee\u6539\u5bc6\u7801 - ${user.username}` }),
                el('button', {
                    className: 'modal-close',
                    textContent: '\u00d7',
                    onClick: () => closeModal('password-modal'),
                }),
            ]),
            el('div', { className: 'modal-body' }, [
                isSelf ? el('div', { className: 'form-group' }, [
                    el('label', { textContent: '\u65e7\u5bc6\u7801' }),
                    el('input', { type: 'password', id: 'old-password', placeholder: '\u8bf7\u8f93\u5165\u65e7\u5bc6\u7801' }),
                ]) : el('p', { className: 'info-text', textContent: '\u7ba1\u7406\u5458\u6b63\u5728\u91cd\u7f6e\u6b64\u7528\u6237\u7684\u5bc6\u7801\u3002' }),
                el('div', { className: 'form-group' }, [
                    el('label', { textContent: '\u65b0\u5bc6\u7801' }),
                    el('input', { type: 'password', id: 'new-password', placeholder: '\u8bf7\u8f93\u5165\u65b0\u5bc6\u7801' }),
                ]),
                el('div', { className: 'form-group' }, [
                    el('label', { textContent: '\u786e\u8ba4\u65b0\u5bc6\u7801' }),
                    el('input', { type: 'password', id: 'confirm-password', placeholder: '\u8bf7\u518d\u6b21\u8f93\u5165\u65b0\u5bc6\u7801' }),
                ]),
            ]),
            el('div', { className: 'modal-footer' }, [
                el('button', {
                    className: 'btn btn-secondary',
                    textContent: '\u53d6\u6d88',
                    onClick: () => closeModal('password-modal'),
                }),
                el('button', {
                    className: 'btn btn-primary',
                    textContent: '\u786e\u8ba4\u4fee\u6539',
                    onClick: () => handleChangePassword(user),
                }),
            ]),
        ]),
    ]);

    document.body.appendChild(overlay);
}

async function handleChangePassword(user) {
    const isSelf = state.currentUser && state.currentUser.id === user.id;
    const old_password = isSelf ? $('#old-password').value : null;
    const new_password = $('#new-password').value;
    const confirm_password = $('#confirm-password').value;

    if (isSelf && !old_password) {
        showToast('\u8bf7\u8f93\u5165\u65e7\u5bc6\u7801', 'warning');
        return;
    }
    if (!new_password) {
        showToast('\u8bf7\u8f93\u5165\u65b0\u5bc6\u7801', 'warning');
        return;
    }
    if (new_password !== confirm_password) {
        showToast('\u4e24\u6b21\u8f93\u5165\u7684\u5bc6\u7801\u4e0d\u4e00\u81f4', 'warning');
        return;
    }

    try {
        await apiFetch(`/users/${user.id}/password`, {
            method: 'PUT',
            body: JSON.stringify({ old_password, new_password }),
        });
        showToast(`\u5bc6\u7801\u4fee\u6539\u6210\u529f${isSelf ? '\uff0c\u8bf7\u91cd\u65b0\u767b\u5f55' : ''}`, 'success');
        closeModal('password-modal');

        if (isSelf) {
            setTimeout(() => {
                window.GoTubeSession.clearAuthState();
                window.location.href = '/';
            }, 1500);
        }
    } catch (err) {
        showToast('\u4fee\u6539\u5931\u8d25: ' + err.message, 'error');
    }
}

window.showUserManagement = showUserManagement;
window.showVideoManagement = showVideoManagement;
window.switchAdminView = switchAdminView;
window.refreshNavTabs = refreshNavTabs;
window.loadUsers = loadUsers;
window.showUserLibraryModal = showUserLibraryModal;
window.renderUsersTable = renderUsersTable;
window.initClickOutsideListener = initClickOutsideListener;

export { showUserManagement, showVideoManagement, switchAdminView, refreshNavTabs, loadUsers, showUserLibraryModal, renderUsersTable, initClickOutsideListener };
