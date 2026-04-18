/**
 * GoTube Admin - 用户管理模块
 * 用户列表加载、创建、编辑、删除、状态切换
 */

/**
 * 刷新导航标签状态
 */
function refreshNavTabs() {
    document.querySelectorAll('.nav-tab').forEach(btn => {
        const label = btn.textContent.trim();
        btn.classList.toggle('active',
            (state.currentView === 'videos' && label === '视频管理') ||
            (state.currentView === 'users' && label === '用户管理') ||
            (state.currentView === 'invites' && label === '邀请码')
        );
    });
}

/**
 * 显示指定后台视图
 */
function switchAdminView(view) {
    const containers = {
        videos: $('#video-view-container'),
        users: $('#user-view-container'),
        invites: $('#invite-view-container'),
    };

    Object.entries(containers).forEach(([name, container]) => {
        if (!container) return;
        container.style.display = name === view ? 'block' : 'none';
        container.style.opacity = name === view ? '1' : '0';
        container.style.transition = 'opacity 0.15s ease';
    });

    state.currentView = view;
    state.isTransitioning = false;
    refreshNavTabs();
    if (view === 'videos') {
        window.updateBatchBar();
    } else {
        const bar = $('#batch-bar');
        const deleteBtnNav = $('#batch-delete-btn');
        if (bar) bar.classList.remove('active');
        if (deleteBtnNav) deleteBtnNav.disabled = true;
    }
}

/**
 * 切换到用户管理视图（CSS 显示/隐藏，无布局抖动）
 */
async function showUserManagement() {
    // 如果已经在用户管理视图，刷新用户列表
    if (state.currentView === 'users') {
        loadUsers(true);
        return;
    }

    if (state.currentUser && state.currentUser.role !== 'admin') {
        showToast('权限不足', 'error');
        return;
    }

    document.title = 'GoTube Admin - 用户管理';
    switchAdminView('users');
    loadUsers();
}

/**
 * 返回视频管理视图（CSS 显示/隐藏，无布局抖动）
 */
function showVideoManagement() {
    // 如果已经在视频管理视图，直接返回
    if (state.currentView === 'videos') return;

    document.title = 'GoTube Admin - 视频管理';
    switchAdminView('videos');
}

/**
 * 初始化点击外部区域返回视频管理的事件监听
 */
window._clickOutsideListenerInitialized = false;

function initClickOutsideListener() {
    return;
    // 避免重复绑定
    if (window._clickOutsideListenerInitialized) return;

    document.addEventListener('click', (e) => {
        // 只在用户管理视图时生效
        if (state.currentView !== 'users') return;
        // 如果正在过渡中，阻止立即返回
        if (state.isTransitioning) return;
        // 如果有模态框打开，不触发返回
        if (document.querySelector('.modal.active')) return;

        const userContainer = $('#user-view-container');
        // 如果点击的不在用户管理区域内，就返回视频管理
        if (userContainer && !userContainer.contains(e.target)) {
            showVideoManagement();
        }
    });

    window._clickOutsideListenerInitialized = true;
}

/**
 * 加载用户列表（支持缓存）
 */
async function loadUsers(forceReload = false) {
    // 如果有缓存且不强制重新加载，直接使用缓存
    if (state.usersLoaded && !forceReload && state.users.length > 0) {
        renderUsersTable(state.users);
        return;
    }

    // 显示加载状态
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

/**
 * 渲染用户表格
 */
function renderUsersTable(users) {
    const slot = $('#users-table-slot');
    if (!slot) return;

    if (users.length === 0) {
        slot.innerHTML = '<div class="empty-state">暂无用户</div>';
        return;
    }

    // 创建容器，包含新增按钮和表格
    const container = el('div', { className: 'user-table-wrapper' });

    // 新增用户按钮
    const addButton = el('button', {
        className: 'btn btn-primary',
        textContent: '➕ 新增用户',
        onClick: () => showUserEditModal(),
        style: 'margin-bottom: 16px;'
    });
    container.appendChild(addButton);

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
            ])
        ]),
        el('tbody', {}, users.map(user => {
            const isSelf = state.currentUser && state.currentUser.id === user.id;
            const isSystemAccount = user.is_system_account || user.role === 'admin';

            return el('tr', { className: user.is_active ? '' : 'inactive' }, [
                el('td', { textContent: user.id }),
                el('td', { textContent: isSystemAccount ? `管理员 ${user.username}` : user.username + (isSelf ? ' (我)' : '') }),
                el('td', { textContent: formatRole(user.role) }),
                el('td', {}, [
                    el('span', {
                        className: `status-badge ${user.is_active ? 'active' : 'inactive'}`,
                        textContent: user.is_active ? '启用' : '禁用'
                    })
                ]),
                el('td', { textContent: String(user.video_count || 0) }),
                el('td', {
                    textContent: user.role === 'admin'
                        ? '不限'
                        : `${formatBytes(user.storage_used_bytes || 0)} / ${formatUserQuota(user.storage_quota_mb)}`,
                }),
                el('td', { textContent: user.last_login ? new Date(user.last_login).toLocaleString() : '从未登录' }),
                el('td', { className: 'user-actions' }, [
                    isSystemAccount ? null : el('button', {
                        className: 'action-btn-sm',
                        textContent: '📝 编辑',
                        onClick: (e) => {
                            e.stopPropagation();
                            showUserEditModal(user);
                        },
                    }),
                    isSystemAccount ? null : el('button', {
                        className: 'action-btn-sm',
                        textContent: '🔑 密码',
                        onClick: (e) => {
                            e.stopPropagation();
                            showChangePasswordModal(user);
                        },
                    }),
                    !isSelf && !isSystemAccount ? el('button', {
                        className: `action-btn-sm ${user.is_active ? 'danger' : 'success'}`,
                        textContent: user.is_active ? '🚫 禁用' : '✅ 启用',
                        onClick: (e) => {
                            e.stopPropagation();
                            toggleUserActive(user);
                        },
                    }) : null,
                    !isSelf && !isSystemAccount ? el('button', {
                        className: 'action-btn-sm danger',
                        textContent: '🗑️ 删除',
                        onClick: (e) => {
                            e.stopPropagation();
                            handleDeleteUser(user);
                        },
                    }) : null,
                ])
            ]);
        }))
    ]);

    slot.innerHTML = '';
    container.appendChild(table);
    slot.appendChild(container);
}

/**
 * 格式化角色名
 */
function formatRole(role) {
    const map = {
        'admin': '管理员',
        'user': '普通用户'
    };
    return map[role] || role;
}

function formatUserQuota(quotaMb) {
    if (quotaMb === 0) return '不限';
    if (quotaMb === null || quotaMb === undefined) return '默认';
    return `${quotaMb} MB`;
}

/**
 * 切换用户启用/禁用状态
 */
async function toggleUserActive(user) {
    try {
        await apiFetch(`/users/${user.id}`, {
            method: 'PUT',
            body: JSON.stringify({ is_active: !user.is_active })
        });
        showToast(`用户已${user.is_active ? '禁用' : '启用'}`, 'success');
        // 使缓存失效并重新加载
        invalidateUserCache();
        await loadUsers(true);
    } catch (err) {
        showToast('操作失败: ' + err.message, 'error');
    }
}

/**
 * 删除用户
 */
async function handleDeleteUser(user) {
    if (!confirm(`确定要删除用户 "${user.username}" 吗？此操作不可恢复。`)) return;

    try {
        await apiFetch(`/users/${user.id}`, { method: 'DELETE' });
        showToast('用户已删除', 'success');
        // 使缓存失效并重新加载
        invalidateUserCache();
        await loadUsers(true);
    } catch (err) {
        showToast('删除失败: ' + err.message, 'error');
    }
}

/**
 * 显示用户编辑/创建模态框
 */
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
                        placeholder: '请输入密码'
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

/**
 * 保存用户（创建或更新）
 */
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
                body: JSON.stringify(payload)
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
                body: JSON.stringify({ username, password, role })
            });
            showToast('创建成功', 'success');
            closeModal('user-edit-modal');
        }
        // 使缓存失效并重新加载
        invalidateUserCache();
        await loadUsers(true);
    } catch (err) {
        // 错误时不关闭模态框，显示详细错误信息
        const errorMsg = err.message || '操作失败';
        showToast(errorMsg, 'error');
    }
}

/**
 * 显示修改密码模态框
 */
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
                ]) : el('p', { className: 'info-text', textContent: '管理员正在重置此用户的密码' }),
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

/**
 * 执行修改密码
 */
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
            body: JSON.stringify({ old_password, new_password })
        });
        showToast('密码修改成功' + (isSelf ? '，请重新登录' : ''), 'success');
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

// 导出
window.showUserManagement = showUserManagement;
window.showVideoManagement = showVideoManagement;
window.switchAdminView = switchAdminView;
window.refreshNavTabs = refreshNavTabs;
window.loadUsers = loadUsers;
window.renderUsersTable = renderUsersTable;
window.initClickOutsideListener = initClickOutsideListener;
