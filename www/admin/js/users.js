/**
 * GoTube Admin - 用户管理模块
 * 用户列表加载、创建、编辑、删除、状态切换、用户视频库查看
 */

function refreshNavTabs() {
    document.querySelectorAll('[data-admin-nav]').forEach(btn => {
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
        container.style.opacity = active ? '1' : '0';
        container.style.transition = 'opacity 0.15s ease';
    });

    state.nav.current = view;
    state.currentView = view;
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
        showToast('权限不足', 'error');
        return;
    }

    document.title = 'GoTube Admin - 用户';
    switchAdminView('users');
    await loadUsers(state.usersLoaded);
}

async function showVideoManagement() {
    document.title = 'GoTube Admin - 全局媒体';
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
        renderUsersTable(state.users);
        return;
    }

    const slot = $('#users-table-slot');
    if (slot) {
        slot.innerHTML = '<div class="loading">加载中</div>';
    }

    try {
        const users = await apiFetch('/users');
        state.users = users;
        state.usersLoaded = true;
        renderUsersTable(users);
    } catch (err) {
        console.error('加载用户列表失败:', err);
        if (slot) {
            slot.innerHTML = `<div class="error">加载失败: ${err.message}</div>`;
        }
    }
}

function renderUsersTable(users) {
    const slot = $('#users-table-slot');
    if (!slot) return;

    if (users.length === 0) {
        slot.innerHTML = '<div class="empty-state">暂无用户</div>';
        return;
    }

    const container = el('div', { className: 'user-table-wrapper' });
    container.appendChild(el('div', { className: 'admin-section-header' }, [
        el('div', {}, [
            el('h2', { textContent: '用户' }),
            el('p', {
                className: 'info-text',
                textContent: '用户页只处理账号状态、容量和用户个人视频库入口，不直接混入全局媒体卡片。',
            }),
        ]),
        el('button', {
            className: 'btn btn-primary',
            textContent: '新增用户',
            onClick: () => showUserEditModal(),
        }),
    ]));

    const table = el('table', { className: 'users-table' }, [
        el('thead', {}, [
            el('tr', {}, [
                el('th', { textContent: 'ID' }),
                el('th', { textContent: '用户名' }),
                el('th', { textContent: '角色' }),
                el('th', { textContent: '状态' }),
                el('th', { textContent: '视频数' }),
                el('th', { textContent: '容量' }),
                el('th', { textContent: '最后登录' }),
                el('th', { textContent: '操作' }),
            ]),
        ]),
        el('tbody', {}, users.map(user => {
            const isSelf = state.currentUser && state.currentUser.id === user.id;
            const isSystemAccount = user.is_system_account || user.role === 'admin';

            return el('tr', { className: user.is_active ? '' : 'inactive' }, [
                el('td', { textContent: user.id }),
                el('td', {
                    textContent: isSystemAccount
                        ? `管理员 ${user.username}`
                        : `${user.username}${isSelf ? ' (我)' : ''}`,
                }),
                el('td', { textContent: formatRole(user.role) }),
                el('td', {}, [
                    el('span', {
                        className: `status-badge ${user.is_active ? 'active' : 'inactive'}`,
                        textContent: user.is_active ? '启用' : '禁用',
                    }),
                ]),
                el('td', { textContent: String(user.video_count || 0) }),
                el('td', {
                    textContent: user.role === 'admin'
                        ? '不限'
                        : `${formatBytes(user.storage_used_bytes || 0)} / ${formatUserQuota(user.storage_quota_mb)}`,
                }),
                el('td', { textContent: user.last_login ? new Date(user.last_login).toLocaleString('zh-CN') : '从未登录' }),
                el('td', { className: 'user-actions' }, [
                    el('button', {
                        className: 'action-btn-sm',
                        textContent: '视频库',
                        onClick: (e) => {
                            e.stopPropagation();
                            showUserLibraryModal(user);
                        },
                    }),
                    isSystemAccount ? null : el('button', {
                        className: 'action-btn-sm',
                        textContent: '编辑',
                        onClick: (e) => {
                            e.stopPropagation();
                            showUserEditModal(user);
                        },
                    }),
                    isSystemAccount ? null : el('button', {
                        className: 'action-btn-sm',
                        textContent: '密码',
                        onClick: (e) => {
                            e.stopPropagation();
                            showChangePasswordModal(user);
                        },
                    }),
                    !isSelf && !isSystemAccount ? el('button', {
                        className: `action-btn-sm ${user.is_active ? 'danger' : 'success'}`,
                        textContent: user.is_active ? '禁用' : '启用',
                        onClick: (e) => {
                            e.stopPropagation();
                            toggleUserActive(user);
                        },
                    }) : null,
                    !isSelf && !isSystemAccount ? el('button', {
                        className: 'action-btn-sm danger',
                        textContent: '删除',
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
    container.appendChild(table);
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
                    textContent: `${user.username} 的视频库`,
                }),
                el('button', {
                    className: 'modal-close',
                    textContent: '×',
                    onClick: () => closeModal('user-library-modal'),
                }),
            ]),
            el('div', { className: 'modal-body', id: 'user-library-body' }, [
                el('div', { className: 'loading', textContent: '加载中' }),
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
            body.innerHTML = `<div class="error">加载失败: ${err.message}</div>`;
        }
    }
}

function renderUserLibraryModal() {
    const body = $('#user-library-body');
    if (!body) return;

    const items = state.userLibrary.items || [];
    body.innerHTML = '';

    if (items.length === 0) {
        body.appendChild(el('div', { className: 'empty-state', textContent: '该用户暂无视频' }));
        return;
    }

    const list = el('div', { className: 'user-library-list' });
    items.forEach(item => {
        list.appendChild(el('article', { className: 'user-library-item' }, [
            el('div', { className: 'user-library-thumb' }, [
                item.thumbnail_url
                    ? el('img', { src: item.thumbnail_url, alt: item.title, loading: 'lazy' })
                    : el('div', { className: 'preview-thumb-empty', textContent: '🎬' }),
            ]),
            el('div', { className: 'user-library-main' }, [
                el('div', { className: 'preview-title', textContent: item.title || '未命名视频' }),
                el('div', { className: 'user-library-meta' }, [
                    el('span', { textContent: formatBytes(item.size || 0) }),
                    el('span', { textContent: item.source || 'Unknown' }),
                    el('span', { textContent: item.saved_at ? new Date(item.saved_at).toLocaleString('zh-CN') : '无保存时间' }),
                ]),
                el('div', { className: 'video-asset-stats' }, [
                    el('span', { textContent: item.share_enabled ? '分享已开启' : '分享未开启' }),
                ]),
            ]),
            el('div', { className: 'user-library-actions' }, [
                el('button', {
                    className: 'action-btn',
                    textContent: '播放',
                    onClick: () => window.showPlayerModal(item),
                }),
                el('button', {
                    className: 'action-btn share',
                    textContent: '分享',
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
        admin: '管理员',
        user: '普通用户',
    };
    return map[role] || role;
}

function formatUserQuota(quotaMb) {
    if (quotaMb === 0) return '不限';
    if (quotaMb === null || quotaMb === undefined) return '默认';
    return `${quotaMb} MB`;
}

async function toggleUserActive(user) {
    try {
        await apiFetch(`/users/${user.id}`, {
            method: 'PUT',
            body: JSON.stringify({ is_active: !user.is_active }),
        });
        showToast(`用户已${user.is_active ? '禁用' : '启用'}`, 'success');
        invalidateUserCache();
        await loadUsers(true);
    } catch (err) {
        showToast('操作失败: ' + err.message, 'error');
    }
}

async function handleDeleteUser(user) {
    if (!confirm(`确定要删除用户 "${user.username}" 吗？此操作不可恢复。`)) return;

    try {
        await apiFetch(`/users/${user.id}`, { method: 'DELETE' });
        showToast('用户已删除', 'success');
        invalidateUserCache();
        await loadUsers(true);
    } catch (err) {
        showToast('删除失败: ' + err.message, 'error');
    }
}

function showUserEditModal(user = null) {
    const isEdit = !!user;
    const title = isEdit ? '编辑用户' : '新增用户';

    const overlay = el('div', { className: 'modal active', id: 'user-edit-modal' }, [
        el('div', { className: 'modal-content modal-sm' }, [
            el('div', { className: 'modal-header' }, [
                el('div', { className: 'modal-title', textContent: title }),
                el('button', {
                    className: 'modal-close',
                    textContent: '×',
                    onClick: () => closeModal('user-edit-modal'),
                }),
            ]),
            el('div', { className: 'modal-body' }, [
                el('div', { className: 'form-group' }, [
                    el('label', { textContent: '用户名' }),
                    el('input', {
                        type: 'text',
                        id: 'edit-username',
                        value: user ? user.username : '',
                        placeholder: '请输入用户名',
                        ...(isEdit ? { disabled: true } : {}),
                    }),
                ]),
                !isEdit ? el('div', { className: 'form-group' }, [
                    el('label', { textContent: '密码' }),
                    el('input', {
                        type: 'password',
                        id: 'edit-password',
                        placeholder: '请输入密码',
                    }),
                ]) : null,
                el('div', { className: 'form-group' }, [
                    el('label', { textContent: '角色' }),
                    el('select', { id: 'edit-role' }, [
                        el('option', { value: 'user', textContent: '普通用户', selected: user ? user.role === 'user' : true }),
                    ]),
                ]),
                el('div', { className: 'form-group' }, [
                    el('label', { textContent: '视频库容量 MB' }),
                    el('input', {
                        type: 'number',
                        id: 'edit-storage-quota',
                        min: '0',
                        value: user && user.storage_quota_mb !== null && user.storage_quota_mb !== undefined ? String(user.storage_quota_mb) : '',
                        placeholder: '留空使用默认值，0 表示不限',
                    }),
                ]),
            ]),
            el('div', { className: 'modal-footer' }, [
                el('button', {
                    className: 'btn btn-secondary',
                    textContent: '取消',
                    onClick: () => closeModal('user-edit-modal'),
                }),
                el('button', {
                    className: 'btn btn-primary',
                    textContent: '保存',
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
    const role = $('#edit-role').value;
    const quotaInput = $('#edit-storage-quota');
    const quotaRaw = quotaInput ? quotaInput.value.trim() : '';

    if (!username) {
        showToast('请输入用户名', 'warning');
        return;
    }

    try {
        if (isEdit) {
            const payload = { username, role };
            if (quotaRaw === '') {
                payload.storage_quota_mb = null;
            } else {
                const quotaMb = Number.parseInt(quotaRaw, 10);
                if (!Number.isInteger(quotaMb) || quotaMb < 0) {
                    showToast('容量必须为空、0 或正整数', 'warning');
                    return;
                }
                payload.storage_quota_mb = quotaMb;
            }
            await apiFetch(`/users/${user.id}`, {
                method: 'PUT',
                body: JSON.stringify(payload),
            });
            showToast('更新成功', 'success');
            closeModal('user-edit-modal');
        } else {
            const password = $('#edit-password').value;
            if (!password) {
                showToast('请输入密码', 'warning');
                return;
            }
            await apiFetch('/users', {
                method: 'POST',
                body: JSON.stringify({ username, password, role }),
            });
            showToast('创建成功', 'success');
            closeModal('user-edit-modal');
        }
        invalidateUserCache();
        await loadUsers(true);
    } catch (err) {
        showToast(err.message || '操作失败', 'error');
    }
}

function showChangePasswordModal(user) {
    const isSelf = state.currentUser && state.currentUser.id === user.id;

    const overlay = el('div', { className: 'modal active', id: 'password-modal' }, [
        el('div', { className: 'modal-content modal-sm' }, [
            el('div', { className: 'modal-header' }, [
                el('div', { className: 'modal-title', textContent: `修改密码 - ${user.username}` }),
                el('button', {
                    className: 'modal-close',
                    textContent: '×',
                    onClick: () => closeModal('password-modal'),
                }),
            ]),
            el('div', { className: 'modal-body' }, [
                isSelf ? el('div', { className: 'form-group' }, [
                    el('label', { textContent: '旧密码' }),
                    el('input', { type: 'password', id: 'old-password', placeholder: '请输入旧密码' }),
                ]) : el('p', { className: 'info-text', textContent: '管理员正在重置此用户的密码。' }),
                el('div', { className: 'form-group' }, [
                    el('label', { textContent: '新密码' }),
                    el('input', { type: 'password', id: 'new-password', placeholder: '请输入新密码' }),
                ]),
                el('div', { className: 'form-group' }, [
                    el('label', { textContent: '确认新密码' }),
                    el('input', { type: 'password', id: 'confirm-password', placeholder: '请再次输入新密码' }),
                ]),
            ]),
            el('div', { className: 'modal-footer' }, [
                el('button', {
                    className: 'btn btn-secondary',
                    textContent: '取消',
                    onClick: () => closeModal('password-modal'),
                }),
                el('button', {
                    className: 'btn btn-primary',
                    textContent: '确认修改',
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
        showToast('请输入旧密码', 'warning');
        return;
    }
    if (!new_password) {
        showToast('请输入新密码', 'warning');
        return;
    }
    if (new_password !== confirm_password) {
        showToast('两次输入的密码不一致', 'warning');
        return;
    }

    try {
        await apiFetch(`/users/${user.id}/password`, {
            method: 'PUT',
            body: JSON.stringify({ old_password, new_password }),
        });
        showToast(`密码修改成功${isSelf ? '，请重新登录' : ''}`, 'success');
        closeModal('password-modal');

        if (isSelf) {
            setTimeout(() => {
                window.GoTubeSession.clearAuthState();
                window.location.href = '/';
            }, 1500);
        }
    } catch (err) {
        showToast('修改失败: ' + err.message, 'error');
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
