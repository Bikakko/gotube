/**
 * GoTube 下载页 (/7777) - 客户端脚本
 */
(function () {
    'use strict';

    const $ = (s) => document.querySelector(s);

    let clientId = sessionStorage.getItem('gotube_client_id') || 'c_' + Math.random().toString(36).substr(2, 9);
    sessionStorage.setItem('gotube_client_id', clientId);

    // ── 匿名用户 Session 管理 ──
    // 使用 localStorage 持久化，刷新页面时复用
    const GUEST_SESSION_STORAGE_KEY = 'gotube_guest_session_id';
    let guestSessionId = localStorage.getItem(GUEST_SESSION_STORAGE_KEY);
    if (!guestSessionId) {
        guestSessionId = 'guest_' + Date.now().toString(36) + '_' + Math.random().toString(36).substring(2, 9);
        localStorage.setItem(GUEST_SESSION_STORAGE_KEY, guestSessionId);
        console.log('[Session] 创建新 session:', guestSessionId);
    } else {
        console.log('[Session] 复用已有 session:', guestSessionId);
    }

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
                // 游客文件：显示下载按钮（分享无意义，关闭即删除）
                // 登录用户文件：显示分享按钮
                const isGuestFile = t.filename.startsWith('temp_guest/');
                if (isGuestFile) {
                    actions += `<button class="task-btn download" onclick="window.DownloadPage.downloadGuest('${t.task_id}')">⬇ 下载</button>`;
                } else {
                    actions += `<button class="task-btn share" onclick="window.DownloadPage.copyShareLink('${t.task_id}')">🔗 分享</button>`;
                }
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

        // 根据是否为 guest 文件选择 URL
        let videoUrl;
        if (t.filename && t.filename.startsWith('temp_guest/')) {
            // 检查是否为去重文件（DUPLICATE/ 标记）
            const isDuplicate = t.filename.includes('/DUPLICATE/');
            if (isDuplicate) {
                // 去重文件：直接使用主视频库的 hash URL
                videoUrl = `/watch?v=${t.file_hash}`;
            } else {
                // guest 文件：去掉 temp_guest/{session_id}/ 前缀
                const relativePath = t.filename.replace(/^temp_guest\/[^\/]+\//, '');
                videoUrl = `/api/guest-downloads/stream/${guestSessionId}/${encodeURIComponent(relativePath)}`;
            }
        } else {
            videoUrl = `/watch?v=${t.file_hash}`;
        }
        
        const shareUrl = `${location.origin}/watch?v=${t.file_hash}`;

        $('#modal-title').textContent = t.title || '未知标题';
        $('#modal-video').innerHTML = `<video src="${videoUrl}" controls autoplay style="width:100%;background:#000"></video>`;
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
            // 已登录用户不传 session_id，下载至主目录；游客传 session_id，下载至临时目录
            const body = { url };
            if (!isLoggedIn) {
                body.session_id = guestSessionId;
            }

            const res = await fetch(`/api/tasks?client_id=${clientId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
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
        ws = new WebSocket(`${proto}//${location.host}/ws?client_id=${clientId}&session_id=${guestSessionId}`);

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

            // 3秒后重连（高延迟网络下更快尝试重连）
            setTimeout(() => {
                connectWS();
            }, 3000);
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

    /**
     * 下载 guest 临时文件
     */
    function downloadGuest(id) {
        const t = tasks[id];
        if (!t || !t.filename) return;

        // 检查是否为去重文件（DUPLICATE/ 标记）
        const isDuplicate = t.filename.includes('/DUPLICATE/');
        if (isDuplicate) {
            // 去重文件：使用主视频库的下载 API
            const downloadUrl = `/watch?v=${t.file_hash}`;
            const a = document.createElement('a');
            a.href = downloadUrl;
            a.download = t.title || 'video';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            return;
        }

        // 去掉 temp_guest/{session_id}/ 前缀
        const relativePath = t.filename.replace(/^temp_guest\/[^\/]+\//, '');
        const downloadUrl = `/api/guest-downloads/stream/${guestSessionId}/${encodeURIComponent(relativePath)}`;

        // 触发浏览器下载
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = t.title || 'video';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }

    // 暴露全局 API
    window.DownloadPage = {
        retryTask,
        openModal,
        closeModal,
        copyShare,
        copyShareLink,
        downloadGuest,
        closeLoginModal,
        checkAndTransferGuestDownloads
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

            // 登录后检测是否有游客临时下载
            await checkAndTransferGuestDownloads();
        } catch (err) {
            errorEl.textContent = err.message || '登录失败，请重试';
        } finally {
            btn.disabled = false;
            btn.textContent = '登录';
        }
    }

    /**
     * 检测并转移游客临时下载
     */
    async function checkAndTransferGuestDownloads() {
        try {
            // 获取当前 session 的下载数量
            const countRes = await fetch(`/api/guest-downloads/${guestSessionId}/count`);
            if (!countRes.ok) {
                console.warn('获取游客下载数量失败');
                return;
            }

            const countData = await countRes.json();
            const count = countData.count;

            if (count === 0) {
                console.log('没有游客临时下载，无需转移');
                return;
            }

            setStatus('🔄 正在转移视频到视频库...', '#58a6ff');

            // 调用转移 API
            const transferRes = await fetch(`/api/guest-downloads/${guestSessionId}/transfer?client_id=${clientId}`, {
                method: 'POST',
            });

            if (!transferRes.ok) {
                const errData = await transferRes.json();
                throw new Error(errData.detail || '转移失败');
            }

            const transferData = await transferRes.json();
            const transferredCount = transferData.transferred_count;

            // 使用后端返回的 updated_tasks 更新本地任务数据
            if (transferData.updated_tasks && transferData.updated_tasks.length > 0) {
                transferData.updated_tasks.forEach(updatedTask => {
                    if (tasks[updatedTask.task_id]) {
                        tasks[updatedTask.task_id] = updatedTask;
                    }
                });
                // 重新渲染任务列表
                renderTasks();
            } else {
                // 如果没有返回 updated_tasks，刷新整个任务列表
                await loadTasks();
            }

            // 显示 Toast 提示
            showToast(`✅ 已转移 ${transferredCount} 个视频到视频库`, '#3fb950');

        } catch (err) {
            console.error('转移游客下载失败:', err);
            showToast('⚠️ 转移失败: ' + err.message, '#d29922');
        }
    }

    /**
     * 显示不打断操作的 Toast 提示
     */
    function showToast(message, color = '#3fb950', duration = 3000) {
        // 创建 Toast 元素
        const toast = document.createElement('div');
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0, 0, 0, 0.85);
            color: ${color};
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 14px;
            z-index: 10000;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.3s ease;
        `;
        toast.textContent = message;
        document.body.appendChild(toast);

        // 淡入
        requestAnimationFrame(() => {
            toast.style.opacity = '1';
        });

        // 自动消失
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => {
                document.body.removeChild(toast);
            }, 300);
        }, duration);
    }

})();
