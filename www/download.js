/**
 * GoTube 下载页 (/7777) - 客户端脚本
 */
(function () {
    'use strict';

    const $ = (s) => document.querySelector(s);

    let clientId = sessionStorage.getItem('gotube_client_id') || 'c_' + Math.random().toString(36).substr(2, 9);
    sessionStorage.setItem('gotube_client_id', clientId);

    const tasks = {};
    let ws = null;

    function setStatus(msg, color = '#8b949e') {
        const el = $('#status');
        el.textContent = msg;
        el.style.color = color;
    }

    function fmtBytes(b) {
        if (!b) return '';
        const u = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(b) / Math.log(1024));
        return (b / Math.pow(1024, i)).toFixed(1) + ' ' + u[i];
    }

    function fmtETA(s) {
        if (!s) return '';
        const m = Math.floor(s / 60);
        return m > 0 ? `${m}分${s % 60}秒` : `${s}秒`;
    }

    function renderTasks() {
        const list = $('#task-list');
        const arr = Object.values(tasks).sort((a, b) => {
            if (a.status === 'downloading' && b.status !== 'downloading') return -1;
            if (b.status === 'downloading' && a.status !== 'downloading') return 1;
            return new Date(b.created_at) - new Date(a.created_at);
        });

        if (arr.length === 0) {
            list.innerHTML = '';
            return;
        }

        list.innerHTML = '';
        const labels = {
            pending: '排队中',
            downloading: '下载中',
            completed: '已完成',
            failed: '失败',
            duplicate: '已去重'
        };

        arr.forEach(t => {
            const pct = Math.round(t.progress);
            const sp = document.createElement('div');
            sp.className = 'task';

            let html = `<div style="display:flex;justify-content:space-between">
                <div class="task-title">${t.title || '获取信息中...'}</div>
                <span class="task-status status-${t.status}">${labels[t.status] || t.status}</span>
            </div>`;

            html += `<div class="progress-bg"><div class="progress-fill" style="width:${pct}%"></div></div>`;

            // 卡片内状态信息
            let metaParts = [];
            metaParts.push(`${pct}%`);

            if (t.status === 'downloading') {
                if (t.speed) metaParts.push(`⚡ ${fmtBytes(t.speed)}/s`);
                if (t.eta && t.total_bytes) metaParts.push(`⏱ ${fmtETA(t.eta)}`);
                if (t.downloaded_bytes && !t.total_bytes) metaParts.push(`📦 ${fmtBytes(t.downloaded_bytes)}`);
            }
            if ((t.status === 'completed' || t.status === 'duplicate') && t.file_hash) {
                metaParts.push(`🔒 ${t.file_hash}`);
            }
            if (t.status === 'failed' && t.error) {
                metaParts.push(`❌ ${t.error}`);
            }

            html += `<div class="progress-info"><span>${metaParts.join(' ')}</span><span></span></div>`;

            // 操作按钮
            let actions = '<div class="task-actions">';
            if (t.status === 'completed' && t.filename) {
                actions += `<button class="task-btn play" onclick="window.DownloadPage.openModal('${t.task_id}')">▶ 播放</button>`;
                actions += `<button class="task-btn share" onclick="window.DownloadPage.copyShareLink('${t.task_id}')">🔗 分享</button>`;
            }
            if (t.status === 'failed') {
                actions += `<button class="task-btn retry" onclick="window.DownloadPage.retryTask('${t.task_id}')">🔄 重试</button>`;
            }
            actions += '</div>';
            html += actions;

            sp.innerHTML = html;
            list.appendChild(sp);
        });
    }

    async function retryTask(id) {
        const t = tasks[id];
        if (!t) return;

        // 立即更新本地状态为 pending
        t.status = 'pending';
        t.progress = 0;
        t.error = '';
        t.speed = 0;
        t.eta = 0;
        renderTasks();
        setStatus('🔄 重试中...', '#58a6ff');

        try {
            const res = await fetch(`/api/tasks/${id}/retry?client_id=${clientId}`, { method: 'POST' });
            if (!res.ok) {
                const e = await res.json();
                setStatus('❌ 重试失败: ' + (e.detail || '未知错误'), '#f85149');
                // 恢复状态
                t.status = 'failed';
                t.error = e.detail || '';
                renderTasks();
                return;
            }
            // 重试已启动，WebSocket 会推送进度更新
            setTimeout(() => setStatus(''), 3000);
        } catch (e) {
            setStatus('❌ ' + e.message, '#f85149');
            t.status = 'failed';
            renderTasks();
        }
    }

    function openModal(id) {
        const t = tasks[id];
        if (!t || !t.file_hash) return;

        const url = `/watch?v=${t.file_hash}`;
        const shareUrl = `${location.origin}/watch?v=${t.file_hash}`;

        $('#modal-title').textContent = t.title || '未知标题';
        $('#modal-video').innerHTML = `<video src="${url}" controls autoplay style="width:100%;background:#000"></video>`;
        $('#copy-btn').dataset.shareUrl = shareUrl;

        $('#modal').classList.add('active');
    }

    function closeModal() {
        $('#modal').classList.remove('active');
        $('#modal-video').innerHTML = '';
    }

    function copyShare() {
        const shareUrl = $('#copy-btn').dataset.shareUrl;
        if (!shareUrl) return;

        navigator.clipboard.writeText(shareUrl).then(() => {
            const btn = $('#copy-btn');
            btn.textContent = '✅ 已复制';
            setTimeout(() => { btn.textContent = '📋 复制链接'; }, 2000);
        }).catch(() => {
            // fallback
            const input = document.createElement('input');
            input.value = shareUrl;
            document.body.appendChild(input);
            input.select();
            document.execCommand('copy');
            document.body.removeChild(input);
            const btn = $('#copy-btn');
            btn.textContent = '✅ 已复制';
            setTimeout(() => { btn.textContent = '📋 复制链接'; }, 2000);
        });
    }

    function copyShareLink(id) {
        const t = tasks[id];
        if (!t || !t.file_hash) return;

        const shareUrl = `${location.origin}/watch?v=${t.file_hash}`;
        navigator.clipboard.writeText(shareUrl).then(() => {
            setStatus('✅ 链接已复制', '#3fb950');
            setTimeout(() => setStatus(''), 2000);
        }).catch(() => {
            setStatus('❌ 复制失败', '#f85149');
        });
    }

    /**
     * 检查是否为有效输入（排除纯中文、纯符号等无效输入）
     */
    function isValidInput(str) {
        // 必须包含至少一个字母或数字
        return /[a-zA-Z0-9]/.test(str);
    }

    /**
     * 检查是否为本站分享链接（需要拦截的）
     */
    function isShareUrl(url) {
        try {
            // 必须是完整绝对 URL（包含协议）
            const u = new URL(url);
            // 检查是否与本站同源
            if (u.origin !== location.origin) return false;
            // 且路径是播放/管理路径，才视为分享链接
            return u.pathname.startsWith('/watch') || 
                   u.pathname.includes('/admin') ||
                   u.pathname.startsWith('/static');
        } catch {
            // 无法解析为完整 URL 的（如相对路径、无效输入），不是分享链接
            return false;
        }
    }

    async function submit() {
        const url = $('#url-input').value.trim();
        if (!url) {
            setStatus('⚠️ 请输入视频链接', '#d29922');
            return;
        }

        // 检查是否为无效输入（如纯中文、纯符号等）
        if (!isValidInput(url)) {
            setStatus('⚠️ 请输入有效的视频链接地址', '#d29922');
            return;
        }

        // 检查是否为完整 URL（必须以 http/https 开头）
        if (!url.startsWith('http://') && !url.startsWith('https://')) {
            setStatus('⚠️ 链接必须以 http:// 或 https:// 开头', '#d29922');
            return;
        }

        // 检查是否为本站分享链接
        if (isShareUrl(url)) {
            setStatus('⚠️ 这是本站播放链接，无需重复下载', '#d29922');
            return;
        }

        // URL 去重：检查列表中是否已有相同 URL 的任务
        const existingTask = findTaskByUrl(url);
        if (existingTask) {
            handleExistingTask(existingTask);
            return;
        }

        $('#dl-btn').disabled = true;
        $('#dl-btn').textContent = '提交中...';
        setStatus('添加任务中...', '#58a6ff');

        try {
            const res = await fetch(`/api/tasks?client_id=${clientId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });

            if (!res.ok) {
                const e = await res.json();
                if (res.status === 409) {
                    setStatus('⚠️ ' + (e.detail || '该链接已在下载中或已完成'), '#d29922');
                } else {
                    setStatus('❌ ' + (e.detail || '失败'), '#f85149');
                }
                return;
            }

            const data = await res.json();
            tasks[data.task_id] = data;
            setStatus('✅ 已添加', '#3fb950');
            renderTasks();
        } catch (e) {
            setStatus('❌ ' + e.message, '#f85149');
        } finally {
            $('#dl-btn').disabled = false;
            $('#dl-btn').textContent = '下载';
            setTimeout(() => setStatus(''), 2000);
        }
    }

    function findTaskByUrl(url) {
        return Object.values(tasks).find(t => t.url === url);
    }

    function handleExistingTask(task) {
        switch (task.status) {
            case 'pending':
            case 'downloading':
                setStatus('⚠️ 该视频正在下载中', '#d29922');
                break;
            case 'failed':
                setStatus('🔄 自动重试中...', '#58a6ff');
                retryTask(task.task_id);
                break;
            case 'completed':
                setStatus('✅ 该视频已下载完成', '#3fb950');
                break;
            default:
                setStatus('⚠️ 该链接已在列表中', '#d29922');
        }
    }

    async function loadTasks() {
        try {
            const res = await fetch(`/api/tasks?client_id=${clientId}`);
            if (res.ok) {
                (await res.json()).forEach(t => tasks[t.task_id] = t);
                renderTasks();
            }
        } catch (e) {
            console.error(e);
        }
    }

    function connectWS() {
        // 关闭旧连接
        if (ws) {
            ws.close();
            ws = null;
        }

        const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        ws = new WebSocket(`${proto}//${location.host}/ws?client_id=${clientId}`);

        ws.onopen = () => {
            console.log('WebSocket 连接成功');
            setStatus('🟢 已连接', '#3fb950');
            setTimeout(() => setStatus(''), 2000);
        };

        ws.onmessage = (e) => {
            try {
                const d = JSON.parse(e.data);
                
                if (d.type === 'connected') {
                    console.log('WebSocket 连接确认, client_id:', d.client_id);
                } else if (d.type === 'progress') {
                    // 更新任务进度
                    const taskId = d.task_id;
                    const oldTask = tasks[taskId];
                    
                    // 合并进度数据
                    tasks[taskId] = { ...oldTask, ...d };
                    
                    // 重新渲染任务列表
                    renderTasks();
                    
                    // 调试日志
                    if (d.status === 'completed' || d.status === 'failed') {
                        console.log(`任务 ${taskId} ${d.status}:`, d.title);
                    }
                } else if (d.type === 'pong') {
                    // 心跳响应
                } else {
                    console.log('未知消息类型:', d.type, d);
                }
            } catch (e) {
                console.error('WS 消息解析失败:', e);
            }
        };

        ws.onerror = (e) => {
            console.error('WebSocket 错误:', e);
            setStatus('🔴 连接错误', '#f85149');
        };

        ws.onclose = (e) => {
            console.warn(`WebSocket 断开: code=${e.code}, reason=${e.reason}`);
            setStatus('🟡 连接断开，重连中...', '#d29922');
            
            // 5秒后重连
            setTimeout(() => {
                connectWS();
            }, 5000);
        };
        
        // 心跳保活：每30秒发送一次ping
        if (ws._heartbeat) clearInterval(ws._heartbeat);
        ws._heartbeat = setInterval(() => {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'ping' }));
            }
        }, 30000);
    }

    // 绑定事件
    $('#dl-btn').onclick = submit;
    $('#url-input').onkeypress = (e) => { if (e.key === 'Enter') submit(); };
    document.onkeydown = (e) => { if (e.key === 'Escape') { closeModal(); closeLoginModal(); } };

    // 登录相关
    $('#logo-link').onclick = (e) => {
        e.preventDefault();
        handleLogoClick();
    };
    $('#login-submit-btn').onclick = handleLogin;
    $('#login-password').onkeypress = (e) => { if (e.key === 'Enter') handleLogin(); };

    // 初始化
    loadTasks();
    connectWS();
    checkLoginStatus();

    // 暴露全局 API
    window.DownloadPage = {
        retryTask,
        openModal,
        closeModal,
        copyShare,
        copyShareLink,
        closeLoginModal
    };

    // ========== 登录相关功能 ==========

    let isLoggedIn = false;

    async function checkLoginStatus() {
        const token = localStorage.getItem('gotube_admin_token');
        if (!token) {
            isLoggedIn = false;
            updateLogoStyle();
            return;
        }

        try {
            const hiddenPath = window.GOTUBE_HIDDEN_PATH || '7777';
            const apiBase = `/${hiddenPath}/admin/api`;
            const response = await fetch(`${apiBase}/auth/check`, {
                headers: { 'Authorization': `Bearer ${token}` },
            });

            if (!response.ok) {
                throw new Error('Token 无效');
            }

            const data = await response.json();
            isLoggedIn = data.valid && data.user;
            updateLogoStyle();
        } catch (err) {
            console.debug('Check auth failed:', err.message);
            localStorage.removeItem('gotube_admin_token');
            isLoggedIn = false;
            updateLogoStyle();
        }
    }

    function updateLogoStyle() {
        const logoLink = $('#logo-link');
        if (isLoggedIn) {
            logoLink.title = '进入管理页面';
            logoLink.classList.add('logged-in');
        } else {
            logoLink.title = '点击登录';
            logoLink.classList.remove('logged-in');
        }
    }

    function handleLogoClick() {
        if (isLoggedIn) {
            const hiddenPath = window.GOTUBE_HIDDEN_PATH || '7777';
            window.location.href = `/${hiddenPath}/admin`;
        } else {
            showLoginModal();
        }
    }

    function showLoginModal() {
        $('#login-modal').classList.add('active');
        $('#login-username').focus();
        $('#login-error').textContent = '';
    }

    function closeLoginModal() {
        $('#login-modal').classList.remove('active');
        $('#login-username').value = '';
        $('#login-password').value = '';
        $('#login-error').textContent = '';
    }

    async function handleLogin() {
        const user = $('#login-username').value.trim();
        const pass = $('#login-password').value.trim();
        const errorEl = $('#login-error');
        const btn = $('#login-submit-btn');

        if (!user) {
            errorEl.textContent = '请输入用户名';
            $('#login-username').focus();
            return;
        }
        if (!pass) {
            errorEl.textContent = '请输入密码';
            $('#login-password').focus();
            return;
        }

        btn.disabled = true;
        btn.textContent = '登录中...';
        errorEl.textContent = '';

        try {
            const hiddenPath = window.GOTUBE_HIDDEN_PATH || '7777';
            const apiBase = `/${hiddenPath}/admin/api`;
            const response = await fetch(`${apiBase}/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user, pass }),
            });

            if (!response.ok) {
                let msg = '登录失败';
                try {
                    const data = await response.json();
                    msg = data.detail || msg;
                } catch { /* ignore */ }

                if (response.status === 401) {
                    msg = '用户名或密码错误，请重试';
                } else if (response.status === 429) {
                    msg = '登录次数过多，请稍后再试';
                } else if (response.status >= 500) {
                    msg = '服务器错误，请稍后重试';
                }
                throw new Error(msg);
            }

            const data = await response.json();
            localStorage.setItem('gotube_admin_token', data.token);
            isLoggedIn = true;
            updateLogoStyle();
            closeLoginModal();
        } catch (err) {
            errorEl.textContent = err.message || '登录失败，请重试';
        } finally {
            btn.disabled = false;
            btn.textContent = '登录';
        }
    }

})();
