/**
 * GoTube Admin - 用户管理模块
 * 用户列表加载、创建、编辑、删除、状态切换
 */

/**
 * 切换到用户管理视图（CSS 显示/隐藏，无布局抖动）
 */
async function showUserManagement() {
    // 如果已经在用户管理视图，返回视频管理
    if (state.currentView === 'users') {
        showVideoManagement();
        return;
    }

    if (state.currentUser && state.currentUser.role !== 'admin') {
        showToast('权限不足', 'error');
        return;
    }

    // 防止重复切换
    if (state.isTransitioning) return;
    state.isTransitioning = true;

    // 更新视图状态
    state.currentView = 'users';
    document.title = 'GoTube Admin - 用户管理';

    // 获取两个视图容器
    const videoContainer = $('#video-view-container');
    const userContainer = $('#user-view-container');

    if (!videoContainer || !userContainer) {
        state.isTransitioning = false;
        return;
    }

    // 添加淡出效果
    videoContainer.style.opacity = '0';
    videoContainer.style.transition = 'opacity 0.15s ease';

    // 等待淡出完成后切换视图
    setTimeout(() => {
        // 隐藏视频视图，显示用户视图
        videoContainer.style.display = 'none';
        userContainer.style.display = 'block';
        userContainer.style.opacity = '0';

        // 强制重排后淡入
        requestAnimationFrame(() => {
            userContainer.style.transition = 'opacity 0.15s ease';
            userContainer.style.opacity = '1';
        });

        // 重置过渡状态
        setTimeout(() => {
            state.isTransitioning = false;
        }, 150);

        // 加载用户数据（使用缓存）
        loadUsers();
    }, 150);
}

/**
 * 返回视频管理视图（CSS 显示/隐藏，无布局抖动）
 */
function showVideoManagement() {
    // 如果已经在视频管理视图，直接返回
    if (state.currentView === 'videos') return;

    // 防止重复切换
    if (state.isTransitioning) return;
    state.isTransitioning = true;

    // 更新视图状态
    state.currentView = 'videos';
    document.title = 'GoTube Admin - 视频管理';

    // 获取两个视图容器
    const videoContainer = $('#video-view-container');
    const userContainer = $('#user-view-container');

    if (!videoContainer || !userContainer) {
        state.isTransitioning = false;
        return;
    }

    // 添加淡出效果
    userContainer.style.opacity = '0';
    userContainer.style.transition = 'opacity 0.15s ease';

    // 等待淡出完成后切换视图
    setTimeout(() => {
        // 隐藏用户视图，显示视频视图
        userContainer.style.display = 'none';
        videoContainer.style.display = 'block';
        videoContainer.style.opacity = '0';

        // 强制重排后淡入
        requestAnimationFrame(() => {
            videoContainer.style.transition = 'opacity 0.15s ease';
            videoContainer.style.opacity = '1';
        });

        // 重置过渡状态
        setTimeout(() => {
            state.isTransitioning = false;
        }, 150);
    }, 150);
}

/**
 * 初始化点击外部区域返回视频管理的事件监听
 */
window._clickOutsideListenerInitialized = false;

function initClickOutsideListener() {
    // 避免重复绑定
    if (window._clickOutsideListenerInitialized) return;

    document.addEventListener('click', (e) => {
        // 只在用户管理视图时生效
        if (state.currentView !== 'users') return;
        // 如果正在过渡中，阻止立即返回
        if (state.isTransitioning) return;

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

    const table = el('table', { className: 'users-table' }, [
        el('thead', {}, [
            el('tr', {}, [
                el('th', { textContent: 'ID' }),
                el('th', { textContent: '用户名' }),
                el('th', { textContent: '角色' }),
                el('th', { textContent: '状态' }),
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
                el('td', { textContent: user.last_login ? new Date(user.last_login).toLocaleString() : '从未登录' }),
                el('td', { className: 'user-actions' }, [
                    isSystemAccount ? null : el('button', {
                        className: 'action-btn-sm',
                        textContent: '📝 编辑',
                        onClick: () => showUserEditModal(user),
                    }),
                    isSystemAccount ? null : el('button', {
                        className: 'action-btn-sm',
                        textContent: '🔑 密码',
                        onClick: () => showChangePasswordModal(user),
                    }),
                    !isSelf && !isSystemAccount ? el('button', {
                        className: `action-btn-sm ${user.is_active ? 'danger' : 'success'}`,
                        textContent: user.is_active ? '🚫 禁用' : '✅ 启用',
                        onClick: () => toggleUserActive(user),
                    }) : null,
                    !isSelf && !isSystemAccount ? el('button', {
                        className: 'action-btn-sm danger',
                        textContent: '🗑️ 删除',
                        onClick: () => handleDeleteUser(user),
                    }) : null,
                ])
            ]);
        }))
    ]);

    slot.innerHTML = '';
    slot.appendChild(table);
}

/**
 * 格式化角色名
 */
function formatRole(role) {
    const map = {
        'admin': '管理员',
        'user': '普通用户',
        'readonly': '只读用户'
    };
    return map[role] || role;
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
                        el('option', { value: 'readonly', textContent: '只读用户', selected: user ? user.role === 'readonly' : false }),
                    ]),
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

    if (!username) {
        showToast('请输入用户名', 'warning');
        return;
    }

    try {
        if (isEdit) {
            await apiFetch(`/users/${user.id}`, {
                method: 'PUT',
                body: JSON.stringify({ username, role })
            });
            showToast('更新成功', 'success');
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
        }
        closeModal('user-edit-modal');
        // 使缓存失效并重新加载
        invalidateUserCache();
        await loadUsers(true);
    } catch (err) {
        showToast('操作失败: ' + err.message, 'error');
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
                localStorage.removeItem('gotube_admin_token');
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
