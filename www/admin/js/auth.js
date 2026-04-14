/**
 * GoTube Admin - 认证模块
 * 登录、登出、Token 管理
 */

/**
 * 检查当前是否有有效 token
 * @returns {Promise<boolean>} 是否认证通过
 */
async function checkAuth() {
    const token = localStorage.getItem('gotube_admin_token');

    if (!token) {
        // 没有 token，直接显示登录表单
        showLoginForm();
        return false;
    }

    // 增加重试机制，避免网络波动导致误踢
    const maxRetries = 2;
    let lastError = null;
    
    for (let attempt = 0; attempt <= maxRetries; attempt++) {
        try {
            // 有 token，验证是否有效
            const data = await apiFetch('/auth/check');
            // token 有效，保存用户信息
            state.currentUser = data.user;
            return true;
        } catch (err) {
            lastError = err;
            console.warn(`Token 验证失败 (尝试 ${attempt + 1}/${maxRetries + 1}):`, err.message);
            
            // 如果不是 UNAUTHORIZED 错误，可能是网络问题，等待后重试
            if (err.message !== 'UNAUTHORIZED' && attempt < maxRetries) {
                // 等待 500ms 后重试
                await new Promise(resolve => setTimeout(resolve, 500));
                continue;
            }
            
            // UNAUTHORIZED 错误或达到最大重试次数，停止重试
            break;
        }
    }

    // 所有重试都失败了，清除 token 并显示登录表单
    console.error('Token 验证最终失败:', lastError?.message);
    localStorage.removeItem('gotube_admin_token');
    showLoginForm();
    return false;
}

/**
 * 显示登录表单
 */
function showLoginForm() {
    const overlay = el('div', { className: 'login-overlay', id: 'login-overlay' }, [
        el('div', { className: 'login-box' }, [
            el('h2', { className: 'login-title', textContent: '🔐 GoTube 管理登录' }),
            el('div', { className: 'login-form' }, [
                el('input', {
                    className: 'login-input',
                    id: 'login-user',
                    type: 'text',
                    placeholder: '用户名',
                    autocomplete: 'username',
                }),
                el('input', {
                    className: 'login-input',
                    id: 'login-pass',
                    type: 'password',
                    placeholder: '密码',
                    autocomplete: 'current-password',
                }),
                el('div', { className: 'login-error', id: 'login-error' }),
                el('button', {
                    className: 'login-btn',
                    id: 'login-btn',
                    textContent: '登录',
                    onClick: handleLogin,
                }),
            ]),
        ]),
    ]);

    // 回车键登录
    overlay.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            handleLogin();
        }
    });

    document.body.appendChild(overlay);
    $('#login-user')?.focus();
}

/**
 * 隐藏登录表单
 */
function hideLoginForm() {
    const overlay = $('#login-overlay');
    if (overlay) {
        overlay.remove();
    }
}

/**
 * 处理登录
 */
async function handleLogin() {
    const user = $('#login-user')?.value || '';
    const pass = $('#login-pass')?.value || '';
    const errorEl = $('#login-error');
    const btn = $('#login-btn');

    // 清空之前的错误信息
    if (errorEl) errorEl.textContent = '';

    if (!user || !pass) {
        if (errorEl) errorEl.textContent = '⚠️ 请输入用户名和密码';
        return;
    }

    // 禁用按钮防止重复提交
    if (btn) {
        btn.disabled = true;
        btn.textContent = '登录中...';
    }

    try {
        const response = await fetch(`${getApiBase()}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user, pass }),
        });

        // 处理响应
        if (response.status === 401) {
            // 用户名或密码错误
            const error = await response.json().catch(() => ({ detail: '用户名或密码错误' }));
            throw new Error('❌ ' + (error.detail || '用户名或密码错误'));
        }

        if (!response.ok) {
            // 其他服务器错误
            throw new Error('❌ 服务器错误，请稍后重试');
        }

        const data = await response.json();

        if (!data.token) {
            throw new Error('❌ 登录响应异常，请重试');
        }

        // 登录成功
        localStorage.setItem('gotube_admin_token', data.token);
        state.currentUser = data.user;  // 立即更新用户状态
        hideLoginForm();
        window.renderPage();
    } catch (err) {
        // 显示错误信息在表单内
        if (errorEl) {
            errorEl.textContent = err.message || '❌ 登录失败，请重试';
            // 抖动效果提示用户
            errorEl.style.animation = 'none';
            setTimeout(() => {
                errorEl.style.animation = 'shake 0.3s';
            }, 10);
        }
        // 清空密码框
        const passInput = $('#login-pass');
        if (passInput) {
            passInput.value = '';
            passInput.focus();
        }
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = '登录';
        }
    }
}

/**
 * 退出登录
 */
function handleLogout() {
    if (!confirm('确定要退出管理页面吗？')) return;

    localStorage.removeItem('gotube_admin_token');
    location.reload();
}
