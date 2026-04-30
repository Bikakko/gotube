/**
 * GoTube 下载页 - 客户端脚本
 */
(function () {
    'use strict';

    const $ = (s) => document.querySelector(s);

    const session = window.GoTubeSession;
    let clientId = session.getDownloadClientId();
    const hiddenPath = (() => {
        if (window.GOTUBE_HIDDEN_PATH) return window.GOTUBE_HIDDEN_PATH;
        const parts = window.location.pathname.split('/').filter(Boolean);
        return parts[0] || '';
    })();

    // ── 匿名用户 Session 管理 ──
    // 使用 sessionStorage：刷新页面复用，关闭标签页后失效，避免旧路人 session 被新登录用户转存。
    session.dropLegacyGuestLocalStorage();
    let guestSessionId = session.getGuestSessionId();
    console.log('[Session] 当前 session:', guestSessionId);

    const tasks = {};
    let ws = null;
    let reconnectTimer = null;
    let wsGeneration = 0;
    let isLoggedIn = false;
    let currentUser = null;
    let myVideos = [];
    let myQuota = null;
    let libraryPage = 1;
    const libraryPageSize = 8;

    function authHeaders(extra = {}) {
        const token = localStorage.getItem('gotube_admin_token');
        return token ? { ...extra, 'Authorization': `Bearer ${token}` } : extra;
    }

    function isRegularUser() {
        return isLoggedIn && currentUser && currentUser.role === 'user';
    }

    function isLibraryUser() {
        return isLoggedIn && currentUser && (currentUser.role === 'user' || currentUser.role === 'admin');
    }

    function isQuotaError(message = '') {
        return /容量不足|quota/i.test(String(message || ''));
    }

    function setStatus(msg, color = '#8b949e') {
        const el = $('#status');
        el.textContent = msg;
        el.style.color = color;
    }

    function renderActionableErrorActions(container, actions = []) {
        if (!container) return;
        container.replaceChildren();
        actions.forEach((action) => {
            if (!action || typeof action.onClick !== 'function') return;
            const button = document.createElement('button');
            button.type = 'button';
            button.className = `task-btn ${action.className || 'secondary'}`;
            button.textContent = action.label || '';
            button.addEventListener('click', action.onClick);
            container.appendChild(button);
        });
    }

    function clearActionableError() {
        const panel = $('#actionable-error');
        const messageEl = $('#actionable-error-message');
        const actionsEl = $('#actionable-error-actions');
        if (messageEl) messageEl.textContent = '';
        if (actionsEl) actionsEl.replaceChildren();
        if (panel) panel.classList.remove('active');
    }

    function showActionableError({ message, actions = [], context = '' }) {
        const panel = $('#actionable-error');
        const messageEl = $('#actionable-error-message');
        const actionsEl = $('#actionable-error-actions');
        if (!panel || !messageEl || !actionsEl) return;
        messageEl.textContent = message || '';
        panel.dataset.context = context || '';
        renderActionableErrorActions(actionsEl, actions);
        panel.classList.add('active');
    }

    function showLoginError(message, actions = []) {
        const errorEl = $('#login-error');
        const actionsEl = $('#login-error-actions');
        if (errorEl) errorEl.textContent = message || '';
        renderActionableErrorActions(actionsEl, actions);
    }

    function clearLoginError() {
        const errorEl = $('#login-error');
        const actionsEl = $('#login-error-actions');
        if (errorEl) errorEl.textContent = '';
        if (actionsEl) actionsEl.replaceChildren();
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

    function renderTasksSafe(list, arr) {
        list.replaceChildren();
        if (arr.length === 0) return;

        const labels = {
            pending: '排队中',
            downloading: '下载中',
            completed: '已完成',
            failed: '失败',
            cancelled: '已取消',
            duplicate: '已去重'
        };

        arr.forEach(t => {
            const pct = Math.max(0, Math.min(100, Math.round(t.progress || 0)));
            const card = document.createElement('div');
            card.className = 'task';

            const header = document.createElement('div');
            header.style.display = 'flex';
            header.style.justifyContent = 'space-between';

            const title = document.createElement('div');
            title.className = 'task-title';
            title.textContent = t.title || '获取信息中...';

            const status = document.createElement('span');
            const statusClass = t.status === 'cancelled' ? 'status-cancelled' : `status-${t.status}`;
            status.className = `task-status ${statusClass}`;
            status.textContent = labels[t.status] || t.status;
            header.append(title, status);

            const progressBg = document.createElement('div');
            progressBg.className = 'progress-bg';
            const progressFill = document.createElement('div');
            progressFill.className = 'progress-fill';
            progressFill.style.width = `${pct}%`;
            progressBg.appendChild(progressFill);

            const metaParts = [`${pct}%`];

            if (t.status === 'downloading') {
                if (t.speed) metaParts.push(`⚡ ${fmtBytes(t.speed)}/s`);
                if (t.eta && t.total_bytes) metaParts.push(`⏱ ${fmtETA(t.eta)}`);
                if (t.downloaded_bytes && !t.total_bytes) metaParts.push(`📦 ${fmtBytes(t.downloaded_bytes)}`);
            }
            if ((t.status === 'completed' || t.status === 'duplicate') && (t.share_token || t.file_hash)) {
                metaParts.push(`🔒 ${t.share_token ? '用户分享' : t.file_hash}`);
            }
            if (t.status === 'failed' && t.error) {
                metaParts.push(`❌ ${t.error}`);
            }

            const progressInfo = document.createElement('div');
            progressInfo.className = 'progress-info';
            const progressText = document.createElement('span');
            progressText.textContent = metaParts.join(' ');
            progressInfo.append(progressText, document.createElement('span'));

            const actions = document.createElement('div');
            actions.className = 'task-actions';
            const addButton = (className, text, handler) => {
                const button = document.createElement('button');
                button.className = `task-btn ${className}`;
                button.type = 'button';
                button.textContent = text;
                button.addEventListener('click', handler);
                actions.appendChild(button);
            };

            if (t.status === 'completed' && t.filename) {
                addButton('play', '▶ 播放', () => openModal(t.task_id));
                if (t.filename.startsWith('temp_guest/')) {
                    addButton('download', '⬇ 下载', () => downloadGuest(t.task_id));
                } else if (!isLoggedIn) {
                    addButton('share', '🔗 分享', () => copyShareLink(t.task_id));
                    if (t.user_video_item_id) {
                        addButton('download', '⬇ 下载', () => downloadMyVideo({ id: t.user_video_item_id, title: t.title }));
                    }
                } else {
                    if (t.share_token || t.file_hash) {
                        addButton('share', '🔗 分享', () => copyShareLink(t.task_id));
                    }
                    if (t.user_video_item_id) {
                        addButton('download', '⬇ 下载', () => downloadMyVideo({ id: t.user_video_item_id, title: t.title }));
                    }
                    addButton('secondary', '在视频库管理', () => $('#library-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
                }
            }
            if (t.status === 'failed' && !isQuotaError(t.error)) {
                addButton('retry', '🔄 重试', () => retryTask(t.task_id));
            }

            card.append(header, progressBg, progressInfo, actions);
            list.appendChild(card);
        });
    }

    function renderTasks() {
        const list = $('#task-list');
        const arr = Object.values(tasks).sort((a, b) => {
            if (a.status === 'downloading' && b.status !== 'downloading') return -1;
            if (b.status === 'downloading' && a.status !== 'downloading') return 1;
            return new Date(b.created_at) - new Date(a.created_at);
        });

        renderTasksSafe(list, arr);
    }

    function shouldArchiveTaskCard(task) {
        return Boolean(
            task
            && isLibraryUser()
            && (task.status === 'completed' || task.status === 'duplicate')
            && task.user_video_item_id
        );
    }

    function storeTask(task) {
        if (!task || !task.task_id) return false;
        if (shouldArchiveTaskCard(task)) {
            delete tasks[task.task_id];
            return false;
        }
        tasks[task.task_id] = task;
        return true;
    }

    function clearTasks() {
        Object.keys(tasks).forEach(key => delete tasks[key]);
        renderTasks();
    }

    async function getActiveDownloads() {
        const res = await fetch(`/api/tasks/active?client_id=${encodeURIComponent(clientId)}`, {
            headers: authHeaders(),
        });
        if (!res.ok) return [];
        return await res.json();
    }

    async function cancelActiveDownloads() {
        const res = await fetch(`/api/tasks/cancel-active?client_id=${encodeURIComponent(clientId)}`, {
            method: 'POST',
            headers: authHeaders(),
        });
        if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            throw new Error(data.detail || '取消下载失败');
        }
        return await res.json();
    }

    function resetClientSession() {
        clientId = session.resetDownloadClient();
        clearTasks();
    }

    function rotateClientSession() {
        resetClientSession();
        connectWS();
    }

    function rotateGuestSession() {
        guestSessionId = session.rotateGuestSession();
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
            const res = await fetch(`/api/tasks/${id}/retry?client_id=${clientId}`, {
                method: 'POST',
                headers: authHeaders(),
            });
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
        const canPlayGuestFile = Boolean(t && t.filename && t.filename.startsWith('temp_guest/') && !t.filename.includes('/DUPLICATE/'));
        const canPlaySharedFile = Boolean(t && (t.file_hash || t.share_token));
        if (!t || (!canPlayGuestFile && !canPlaySharedFile)) return;

        // 根据是否为 guest 文件选择 URL
        let videoUrl;
        if (canPlayGuestFile) {
            // guest 文件：去掉 temp_guest/{session_id}/ 前缀
            const relativePath = t.filename.replace(/^temp_guest\/[^\/]+\//, '');
            videoUrl = `/api/guest-downloads/stream/${guestSessionId}/${encodeURIComponent(relativePath)}`;
        } else if (t.filename && t.filename.startsWith('temp_guest/')) {
            // 检查是否为去重文件（DUPLICATE/ 标记）
            videoUrl = `/watch?v=${encodeURIComponent(t.share_token || t.file_hash)}`;
        } else {
            videoUrl = `/watch?v=${encodeURIComponent(t.share_token || t.file_hash)}`;
        }
        
        const shareToken = t.share_token || t.file_hash;
        const shareUrl = shareToken
            ? `${location.origin}/watch?v=${encodeURIComponent(shareToken)}`
            : `${location.origin}${videoUrl}`;

        $('#modal-title').textContent = t.title || '未知标题';
        const modalVideo = $('#modal-video');
        modalVideo.replaceChildren();
        const video = document.createElement('video');
        video.src = videoUrl;
        video.controls = true;
        video.autoplay = true;
        video.style.width = '100%';
        video.style.background = '#000';
        modalVideo.appendChild(video);
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
        if (!t || (!t.share_token && !t.file_hash)) return;

        const shareUrl = `${location.origin}/watch?v=${encodeURIComponent(t.share_token || t.file_hash)}`;
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
        clearActionableError();
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
                headers: authHeaders({ 'Content-Type': 'application/json' }),
                body: JSON.stringify(body)
            });

            if (!res.ok) {
                const e = await res.json();
                if (res.status === 409) {
                    setStatus('\u26a0\ufe0f ' + (e.detail || '\u8be5\u94fe\u63a5\u5df2\u5728\u4e0b\u8f7d\u4e2d\u6216\u5df2\u5b8c\u6210'), '#d29922');
                } else {
                    const detail = e.detail || '\u5931\u8d25';
                    setStatus('\u274c ' + detail, '#f85149');
                    showActionableError({
                        message: detail,
                        context: 'submit',
                        actions: [
                            { label: '\u91cd\u8bd5\u63d0\u4ea4', className: 'retry', onClick: submit },
                            {
                                label: '\u6e05\u7a7a\u8f93\u5165',
                                className: 'secondary',
                                onClick: () => {
                                    $('#url-input').value = '';
                                    clearActionableError();
                                    $('#url-input').focus();
                                },
                            },
                        ],
                    });
                }
                return;
            }

            const data = await res.json();
            storeTask(data);
            clearActionableError();
            setStatus('\u2705 \u5df2\u6dfb\u52a0', '#3fb950');
            renderTasks();
            if (isLibraryUser()) loadMyLibrary();
        } catch (e) {
            setStatus('\u274c ' + e.message, '#f85149');
            showActionableError({
                message: e.message || '\u4e0b\u8f7d\u63d0\u4ea4\u5931\u8d25',
                context: 'submit',
                actions: [
                    { label: '\u91cd\u8bd5\u63d0\u4ea4', className: 'retry', onClick: submit },
                ],
            });
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
                (await res.json()).forEach(storeTask);
                renderTasks();
            }
        } catch (e) {
            console.error(e);
        }
    }

    function connectWS() {
        const generation = ++wsGeneration;
        if (reconnectTimer) {
            clearTimeout(reconnectTimer);
            reconnectTimer = null;
        }

        // 关闭旧连接
        if (ws) {
            ws.onclose = null;
            if (ws._heartbeat) clearInterval(ws._heartbeat);
            ws.close();
            ws = null;
        }

        const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const params = new URLSearchParams({ client_id: clientId });
        if (!isLoggedIn) {
            params.set('session_id', guestSessionId);
        }
        ws = new WebSocket(`${proto}//${location.host}/ws?${params.toString()}`);
        const currentWs = ws;

        ws.onopen = () => {
            if (ws !== currentWs || generation !== wsGeneration) return;
            console.log('WebSocket 连接成功');
            setStatus('🟢 已连接', '#3fb950');
            setTimeout(() => setStatus(''), 2000);
        };

        ws.onmessage = (e) => {
            if (ws !== currentWs || generation !== wsGeneration) return;
            try {
                const d = JSON.parse(e.data);
                
                if (d.type === 'connected') {
                    console.log('WebSocket 连接确认, client_id:', d.client_id);
                } else if (d.type === 'progress') {
                    // 更新任务进度
                    const taskId = d.task_id;
                    const oldTask = tasks[taskId];
                    
                    // 合并进度数据
                    storeTask({ ...oldTask, ...d });
                    
                    // 重新渲染任务列表
                    renderTasks();
                    
                    // 调试日志
                    if (d.status === 'completed' || d.status === 'failed') {
                        console.log(`任务 ${taskId} ${d.status}:`, d.title);
                        if (d.status === 'completed' && isLibraryUser()) {
                            loadMyLibrary();
                        }
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
            if (ws !== currentWs || generation !== wsGeneration) return;
            console.error('WebSocket 错误:', e);
            setStatus('🔴 连接错误', '#f85149');
        };

        ws.onclose = (e) => {
            if (currentWs._heartbeat) clearInterval(currentWs._heartbeat);
            if (ws !== currentWs || generation !== wsGeneration) return;
            console.warn(`WebSocket 断开: code=${e.code}, reason=${e.reason}`);
            setStatus('🟡 连接断开，重连中...', '#d29922');

            // 3秒后重连（高延迟网络下更快尝试重连）
            reconnectTimer = setTimeout(() => {
                reconnectTimer = null;
                connectWS();
            }, 3000);
        };
        
        // 心跳保活：每30秒发送一次ping
        currentWs._heartbeat = setInterval(() => {
            if (currentWs.readyState === WebSocket.OPEN) {
                currentWs.send(JSON.stringify({ type: 'ping' }));
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
    $('#show-login-btn').onclick = () => switchAuthMode('login');
    $('#show-register-btn').onclick = () => switchAuthMode('register');
    $('#register-submit-btn').onclick = handleRegister;
    $('#register-password').onkeypress = (e) => { if (e.key === 'Enter') handleRegister(); };
    $('#register-invite').onkeypress = (e) => { if (e.key === 'Enter') handleRegister(); };
    $('#refresh-library-btn').onclick = () => loadMyLibrary();
    $('#logout-btn').onclick = logout;
    $('#profile-btn').onclick = promptUpdateDisplayName;
    $('#password-btn').onclick = promptChangePassword;
    $('#admin-link-btn').onclick = () => {
        window.location.href = `/${hiddenPath}/admin`;
    };

    function applyStableDownloadPageLabels() {
        const profileBtn = $('#profile-btn');
        const passwordBtn = $('#password-btn');
        const displayNameInput = $('#register-display-name');
        if (profileBtn) profileBtn.textContent = '\u4fee\u6539\u6635\u79f0';
        if (passwordBtn) passwordBtn.textContent = '\u4fee\u6539\u5bc6\u7801';
        if (displayNameInput) displayNameInput.placeholder = '\u6635\u79f0';
    }

    // 初始化
    async function init() {
        applyStableDownloadPageLabels();
        await checkLoginStatus();
        await loadTasks();
        connectWS();
    }
    init();

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

    async function loadMyLibrary() {
        if (!isLibraryUser()) {
            myVideos = [];
            myQuota = null;
            libraryPage = 1;
            renderMyLibrary();
            clearActionableError();
            return;
        }

        try {
            const [quotaRes, videosRes] = await Promise.all([
                fetch('/api/me/quota', { headers: authHeaders() }),
                fetch('/api/me/videos', { headers: authHeaders() }),
            ]);
            if (!quotaRes.ok || !videosRes.ok) {
                throw new Error('加载视频库失败');
            }
            myQuota = await quotaRes.json();
            const videosData = await videosRes.json();
            myVideos = videosData.videos || [];
            libraryPage = Math.min(libraryPage, Math.max(1, Math.ceil(myVideos.length / libraryPageSize)));
            clearActionableError();
            renderMyLibrary();
        } catch (err) {
            console.error(err);
            showToast('\u26a0\ufe0f \u52a0\u8f7d\u6211\u7684\u89c6\u9891\u5e93\u5931\u8d25: ' + err.message, '#d29922');
            showActionableError({
                message: err.message || '\u52a0\u8f7d\u89c6\u9891\u5e93\u5931\u8d25',
                context: 'library',
                actions: [
                    { label: '\u91cd\u65b0\u52a0\u8f7d', className: 'retry', onClick: loadMyLibrary },
                    { label: '\u5237\u65b0\u9875\u9762', className: 'secondary', onClick: () => window.location.reload() },
                ],
            });
        }
    }

    function renderMyLibrary() {
        const section = $('#library-section');
        const quotaInfo = $('#quota-info');
        const list = $('#library-list');
        if (!section || !quotaInfo || !list) return;

        section.style.display = isLibraryUser() ? 'block' : 'none';
        list.replaceChildren();
        if (!isLibraryUser()) {
            myVideos = [];
            myQuota = null;
            libraryPage = 1;
            quotaInfo.textContent = '';
            return;
        }

        if (myQuota) {
            const quotaText = myQuota.unlimited
                ? '不限容量'
                : `${fmtBytes(myQuota.storage_used_bytes)} / ${fmtBytes(myQuota.storage_quota_bytes)}`;
            quotaInfo.textContent = `容量：${quotaText}`;
        }

        if (myVideos.length === 0) {
            list.appendChild(Object.assign(document.createElement('div'), {
                className: 'empty-library',
                textContent: '还没有保存到视频库的视频',
            }));
            return;
        }

        const totalPages = Math.max(1, Math.ceil(myVideos.length / libraryPageSize));
        if (libraryPage > totalPages) libraryPage = totalPages;
        const start = (libraryPage - 1) * libraryPageSize;
        const visibleVideos = myVideos.slice(start, start + libraryPageSize);

        visibleVideos.forEach(video => {
            const card = document.createElement('div');
            card.className = 'library-item';

            let preview;
            const thumbnailUrl = video.thumbnail_url || video.thumbnail || '';
            if (thumbnailUrl) {
                preview = document.createElement('img');
                preview.className = 'library-thumb';
                preview.alt = '';
                preview.loading = 'lazy';
                setAuthorizedImage(preview, thumbnailUrl);
            } else {
                preview = document.createElement('div');
                preview.className = 'library-thumb-empty';
                preview.textContent = '暂无预览';
            }

            const body = document.createElement('div');

            const title = document.createElement('div');
            title.className = 'library-title';
            title.textContent = video.title || '未命名视频';

            const meta = document.createElement('div');
            meta.className = 'library-meta';
            const source = sourceFromUrl(video.source_url);
            const savedAt = video.saved_at ? new Date(video.saved_at).toLocaleString('zh-CN') : '';
            meta.textContent = `${fmtBytes(video.size)} · ${source || 'Unknown'} · ${savedAt} · ${video.share_enabled ? '分享已开启' : '分享已关闭'}`;

            const actions = document.createElement('div');
            actions.className = 'library-actions';
            addLibraryButton(actions, 'play', '▶ 播放', () => openLibraryVideo(video));
            addLibraryButton(actions, 'share', '🔗 分享', () => copyLibraryShare(video), !video.share_enabled);
            addLibraryButton(actions, 'download', '⬇ 下载', () => downloadMyVideo(video));
            addLibraryButton(actions, 'retry', video.share_enabled ? '关闭分享' : '开启分享', () => toggleLibraryShare(video));
            addLibraryButton(actions, 'danger', '移除', () => deleteLibraryVideo(video));

            body.append(title, meta, actions);
            card.append(preview, body);
            list.appendChild(card);
        });

        if (totalPages > 1) {
            const pager = document.createElement('div');
            pager.className = 'library-pager';
            const prev = document.createElement('button');
            prev.type = 'button';
            prev.className = 'task-btn secondary';
            prev.textContent = '上一页';
            prev.disabled = libraryPage <= 1;
            prev.addEventListener('click', () => {
                libraryPage -= 1;
                renderMyLibrary();
            });
            const info = document.createElement('span');
            info.textContent = `${libraryPage} / ${totalPages}，共 ${myVideos.length} 个`;
            const next = document.createElement('button');
            next.type = 'button';
            next.className = 'task-btn secondary';
            next.textContent = '下一页';
            next.disabled = libraryPage >= totalPages;
            next.addEventListener('click', () => {
                libraryPage += 1;
                renderMyLibrary();
            });
            pager.append(prev, info, next);
            list.appendChild(pager);
        }
    }

    function addLibraryButton(parent, className, text, handler, disabled = false) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = `task-btn ${className}`;
        button.textContent = text;
        button.disabled = disabled;
        button.addEventListener('click', handler);
        parent.appendChild(button);
    }

    function sourceFromUrl(url) {
        try {
            return new URL(url).hostname || '';
        } catch {
            return '';
        }
    }

    function openLibraryVideo(video) {
        if (!video.share_token) return;
        const videoUrl = `/watch?v=${encodeURIComponent(video.share_token)}`;
        $('#modal-title').textContent = video.title || '未知标题';
        const modalVideo = $('#modal-video');
        modalVideo.replaceChildren();
        const elem = document.createElement('video');
        elem.src = videoUrl;
        elem.controls = true;
        elem.autoplay = true;
        elem.style.width = '100%';
        elem.style.background = '#000';
        modalVideo.appendChild(elem);
        $('#copy-btn').dataset.shareUrl = `${location.origin}/watch?v=${encodeURIComponent(video.share_token)}`;
        $('#modal').classList.add('active');
    }

    function copyLibraryShare(video) {
        if (!video.share_enabled || !video.share_token) return;
        copyText(`${location.origin}/watch?v=${encodeURIComponent(video.share_token)}`, '✅ 分享链接已复制');
    }

    async function toggleLibraryShare(video) {
        try {
            const res = await fetch(`/api/me/videos/${video.id}/share`, {
                method: 'PATCH',
                headers: authHeaders({ 'Content-Type': 'application/json' }),
                body: JSON.stringify({ share_enabled: !video.share_enabled }),
            });
            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.detail || '更新失败');
            }
            await loadMyLibrary();
        } catch (err) {
            showToast('❌ ' + err.message, '#f85149');
        }
    }

    async function deleteLibraryVideo(video) {
        if (!confirm(`确定从我的视频库移除“${video.title || '未命名视频'}”吗？`)) return;
        try {
            const res = await fetch(`/api/me/videos/${video.id}`, {
                method: 'DELETE',
                headers: authHeaders(),
            });
            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.detail || '移除失败');
            }
            await loadMyLibrary();
            showToast('✅ 已从我的视频库移除', '#3fb950');
        } catch (err) {
            showToast('❌ ' + err.message, '#f85149');
        }
    }

    async function downloadMyVideo(video) {
        const itemId = video.id || video.user_video_item_id;
        if (!itemId) return;
        try {
            const res = await fetch(`/api/me/videos/${itemId}/download`, {
                headers: authHeaders(),
            });
            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.detail || '下载失败');
            }
            const blob = await res.blob();
            const filename = filenameFromDisposition(res.headers.get('content-disposition')) || filenameWithExtension(video.title, video.filename);
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } catch (err) {
            showToast('❌ ' + err.message, '#f85149');
        }
    }

    function filenameFromDisposition(disposition) {
        if (!disposition) return '';
        const utfMatch = disposition.match(/filename\*=UTF-8''([^;]+)/i);
        if (utfMatch) return decodeURIComponent(utfMatch[1]);
        const match = disposition.match(/filename="?([^"]+)"?/i);
        return match ? match[1] : '';
    }

    function filenameWithExtension(title, filename) {
        const base = (title || 'video').trim() || 'video';
        const extMatch = (filename || '').match(/\.[A-Za-z0-9]{2,5}$/);
        const ext = extMatch ? extMatch[0] : '.mp4';
        return base.toLowerCase().endsWith(ext.toLowerCase()) ? base : base + ext;
    }

    async function setAuthorizedImage(img, url) {
        if (!url.startsWith('/api/me/')) {
            img.src = url;
            return;
        }
        try {
            const res = await fetch(url, { headers: authHeaders() });
            if (!res.ok) throw new Error('thumbnail unavailable');
            const blob = await res.blob();
            const objectUrl = URL.createObjectURL(blob);
            img.onload = () => URL.revokeObjectURL(objectUrl);
            img.src = objectUrl;
        } catch {
            img.replaceWith(Object.assign(document.createElement('div'), {
                className: 'library-thumb-empty',
                textContent: '暂无预览',
            }));
        }
    }

    function copyText(text, message) {
        navigator.clipboard.writeText(text).then(() => {
            showToast(message, '#3fb950');
        }).catch(() => {
            const input = document.createElement('input');
            input.value = text;
            document.body.appendChild(input);
            input.select();
            document.execCommand('copy');
            document.body.removeChild(input);
            showToast(message, '#3fb950');
        });
    }

    // 暴露全局 API
    window.DownloadPage = {
        retryTask,
        openModal,
        closeModal,
        copyShare,
        copyShareLink,
        downloadGuest,
        loadMyLibrary,
        logout,
        closeLoginModal,
        checkAndTransferGuestDownloads
    };

    // ========== 登录相关功能 ==========

    async function checkLoginStatus() {
        const token = localStorage.getItem('gotube_admin_token');
        if (!token) {
            if (session.wasAuthenticatedClient()) {
                session.clearAuthenticatedClient();
                resetClientSession();
            }
            isLoggedIn = false;
            currentUser = null;
            updateLogoStyle();
            renderMyLibrary();
            return;
        }

        try {
            const apiBase = `/${hiddenPath}/admin/api`;
            const response = await fetch(`${apiBase}/auth/check`, {
                headers: { 'Authorization': `Bearer ${token}` },
            });

            if (!response.ok) {
                throw new Error('Token 无效');
            }

            const data = await response.json();
            isLoggedIn = data.valid && data.user;
            currentUser = data.user || null;
            if (isLoggedIn) {
                session.markAuthenticatedClient();
            }
            updateLogoStyle();
            await loadMyLibrary();
        } catch (err) {
            console.debug('Check auth failed:', err.message);
            clientId = session.clearAuthState({ resetDownloadClient: true });
            clearTasks();
            isLoggedIn = false;
            currentUser = null;
            updateLogoStyle();
            renderMyLibrary();
        }
    }

    function formatIdentityText(user) {
        if (!user) return '';
        return `账号：${user.username} | 昵称：${user.display_name || user.username} | ID：${user.id}`;
    }

    async function promptUpdateDisplayName() {
        if (!isLoggedIn || !currentUser) return;
        const nextName = window.prompt('请输入新的昵称', currentUser.display_name || currentUser.username);
        if (nextName === null) return;
        try {
            const response = await fetch('/api/me/profile', {
                method: 'PATCH',
                headers: authHeaders({ 'Content-Type': 'application/json' }),
                body: JSON.stringify({ display_name: nextName }),
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(data.detail || '修改昵称失败');
            currentUser = data.user || currentUser;
            updateLogoStyle();
            showToast('昵称已更新', '#3fb950');
        } catch (err) {
            showToast(err.message || '修改昵称失败', '#f85149');
        }
    }

    async function promptChangePassword() {
        if (!isRegularUser()) return;
        const oldPassword = window.prompt('请输入当前密码');
        if (oldPassword === null || !oldPassword.trim()) return;
        const newPassword = window.prompt('请输入新密码（至少 6 位）');
        if (newPassword === null || !newPassword.trim()) return;
        const confirmPassword = window.prompt('请再次输入新密码');
        if (confirmPassword !== newPassword) {
            showToast('两次输入的新密码不一致', '#f85149');
            return;
        }
        try {
            const response = await fetch('/api/me/password', {
                method: 'POST',
                headers: authHeaders({ 'Content-Type': 'application/json' }),
                body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(data.detail || '修改密码失败');
            showToast('密码已修改，请重新登录', '#3fb950');
            session.clearAuthState();
            isLoggedIn = false;
            currentUser = null;
            myVideos = [];
            myQuota = null;
            updateLogoStyle();
            renderMyLibrary();
            rotateClientSession();
        } catch (err) {
            showToast(err.message || '修改密码失败', '#f85149');
        }
    }

    function updateLogoStyle() {
        const logoLink = $('#logo-link');
        if (isLibraryUser()) {
            logoLink.title = '查看我的视频库';
            logoLink.classList.add('logged-in');
        } else if (isLoggedIn && currentUser && currentUser.role === 'admin') {
            logoLink.title = '进入管理后台';
            logoLink.classList.add('logged-in');
        } else {
            logoLink.title = '点击登录';
            logoLink.classList.remove('logged-in');
        }
        const sessionBar = $('#session-bar');
        const sessionUser = $('#session-user');
        const adminLink = $('#admin-link-btn');
        const profileBtn = $('#profile-btn');
        const passwordBtn = $('#password-btn');
        if (sessionBar && sessionUser && adminLink) {
            sessionBar.classList.toggle('active', isLoggedIn);
            sessionUser.textContent = currentUser ? formatIdentityText(currentUser) : '';
            adminLink.style.display = currentUser && currentUser.role === 'admin' ? 'inline-flex' : 'none';
        }
        if (profileBtn) profileBtn.style.display = isLoggedIn ? 'inline-flex' : 'none';
        if (passwordBtn) passwordBtn.style.display = isRegularUser() ? 'inline-flex' : 'none';
    }

    function handleLogoClick() {
        if (isLibraryUser()) {
            $('#library-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        } else if (isLoggedIn && currentUser && currentUser.role === 'admin') {
            window.location.href = `/${hiddenPath}/admin`;
        } else {
            showLoginModal();
        }
    }

    function confirmLogoutWithActiveDownloads(count) {
        return new Promise(resolve => {
            const overlay = document.createElement('div');
            overlay.style.cssText = `
                position: fixed;
                inset: 0;
                z-index: 10001;
                background: rgba(0, 0, 0, 0.62);
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            `;

            const dialog = document.createElement('div');
            dialog.style.cssText = `
                width: min(420px, 100%);
                background: #161b22;
                border: 1px solid #30363d;
                border-radius: 8px;
                padding: 20px;
                color: #f0f6fc;
                box-shadow: 0 16px 48px rgba(0, 0, 0, 0.36);
            `;

            const title = document.createElement('h3');
            title.textContent = '有下载正在进行';
            title.style.cssText = 'margin: 0 0 10px; font-size: 18px;';

            const body = document.createElement('p');
            body.textContent = `当前有 ${count} 个下载任务正在进行。请选择退出方式。`;
            body.style.cssText = 'margin: 0 0 18px; color: #8b949e; line-height: 1.6;';

            const actions = document.createElement('div');
            actions.style.cssText = 'display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end;';

            const finish = (action) => {
                document.body.removeChild(overlay);
                document.removeEventListener('keydown', onKeydown);
                resolve(action);
            };
            const onKeydown = (event) => {
                if (event.key === 'Escape') finish('stay');
            };

            const addButton = (text, action, primary = false) => {
                const button = document.createElement('button');
                button.type = 'button';
                button.textContent = text;
                button.style.cssText = `
                    border: 1px solid ${primary ? '#f85149' : '#30363d'};
                    background: ${primary ? '#da3633' : '#21262d'};
                    color: #f0f6fc;
                    border-radius: 8px;
                    padding: 9px 12px;
                    cursor: pointer;
                `;
                button.addEventListener('click', () => finish(action));
                actions.appendChild(button);
            };

            addButton('不退出', 'stay');
            addButton('保留下载并退出', 'keep-downloads');
            addButton('取消下载并退出', 'cancel-downloads', true);

            dialog.append(title, body, actions);
            overlay.appendChild(dialog);
            document.body.appendChild(overlay);
            document.addEventListener('keydown', onKeydown);
        });
    }

    async function logout() {
        let logoutAction = 'logout';
        const activeDownloads = await getActiveDownloads();
        if (activeDownloads.length > 0) {
            logoutAction = await confirmLogoutWithActiveDownloads(activeDownloads.length);
            if (logoutAction === 'stay') return;
        } else if (!confirm('确定要退出登录吗？')) {
            return;
        }

        if (logoutAction === 'cancel-downloads') {
            try {
                await cancelActiveDownloads();
                clearTasks();
            } catch (err) {
                showToast('⚠️ ' + err.message, '#d29922');
                return;
            }
        }

        const token = localStorage.getItem('gotube_admin_token');
        if (token) {
            await fetch(`/${hiddenPath}/admin/api/auth/logout`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
            }).catch(() => {});
        }
        session.clearAuthState();
        isLoggedIn = false;
        currentUser = null;
        myVideos = [];
        myQuota = null;
        libraryPage = 1;
        updateLogoStyle();
        renderMyLibrary();
        rotateClientSession();
        showToast('已退出登录', '#3fb950');
    }

    function showLoginModal() {
        $('#login-modal').classList.add('active');
        switchAuthMode('login');
        $('#login-username').focus();
        clearLoginError();
    }

    function switchAuthMode(mode) {
        const isRegister = mode === 'register';
        $('#auth-modal-title').textContent = isRegister ? '注册' : '登录';
        $('#login-panel').style.display = isRegister ? 'none' : 'block';
        $('#register-panel').style.display = isRegister ? 'block' : 'none';
        $('#show-login-btn').classList.toggle('active', !isRegister);
        $('#show-register-btn').classList.toggle('active', isRegister);
        clearLoginError();
        $('#register-error').textContent = '';
        if (isRegister) {
            $('#register-username').focus();
        } else {
            $('#login-username').focus();
        }
    }

    function closeLoginModal() {
        $('#login-modal').classList.remove('active');
        $('#login-username').value = '';
        $('#login-password').value = '';
        clearLoginError();
        $('#register-username').value = '';
        $('#register-display-name').value = '';
        $('#register-password').value = '';
        $('#register-invite').value = '';
        $('#register-error').textContent = '';
    }

    async function handleLogin() {
        const user = $('#login-username').value.trim();
        const pass = $('#login-password').value.trim();
        const errorEl = $('#login-error');
        const btn = $('#login-submit-btn');

        if (!user) {
            showLoginError('\u8bf7\u8f93\u5165\u7528\u6237\u540d');
            $('#login-username').focus();
            return;
        }
        if (!pass) {
            showLoginError('\u8bf7\u8f93\u5165\u5bc6\u7801');
            $('#login-password').focus();
            return;
        }

        btn.disabled = true;
        btn.textContent = '\u767b\u5f55\u4e2d...';
        clearLoginError();

        try {
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
            const previousUserId = currentUser && currentUser.id;
            localStorage.setItem('gotube_admin_token', data.token);
            session.markAuthenticatedClient();
            isLoggedIn = true;
            currentUser = data.user || null;
            if (previousUserId && currentUser && previousUserId !== currentUser.id) {
                rotateClientSession();
            }
            updateLogoStyle();
            closeLoginModal();

            // 登录后检测是否有游客临时下载。
            await checkAndTransferGuestDownloads();
            if (isLibraryUser()) {
                await loadMyLibrary();
                connectWS();
            } else {
                myVideos = [];
                myQuota = null;
                renderMyLibrary();
                connectWS();
            }
        } catch (err) {
            showLoginError(err.message || '\u767b\u5f55\u5931\u8d25\uff0c\u8bf7\u91cd\u8bd5', [
                { label: '\u91cd\u8bd5\u767b\u5f55', className: 'retry', onClick: handleLogin },
                { label: '\u6e05\u7a7a\u5bc6\u7801', className: 'secondary', onClick: () => { $('#login-password').value = ''; $('#login-password').focus(); } },
            ]);
        } finally {
            btn.disabled = false;
            btn.textContent = '登录';
        }
    }

    async function handleRegister() {
        const username = $('#register-username').value.trim();
        const displayName = $('#register-display-name').value.trim();
        const password = $('#register-password').value.trim();
        const inviteCode = $('#register-invite').value.trim();
        const errorEl = $('#register-error');
        const btn = $('#register-submit-btn');

        if (!/^[A-Za-z0-9_-]{3,32}$/.test(username)) {
            errorEl.textContent = '用户名需为 3-32 位字母、数字、下划线或短横线';
            $('#register-username').focus();
            return;
        }
        if (!displayName) {
            errorEl.textContent = '\u8bf7\u8f93\u5165\u6635\u79f0';
            $('#register-display-name').focus();
            return;
        }
        if (password.length < 6) {
            errorEl.textContent = '密码至少 6 位';
            $('#register-password').focus();
            return;
        }
        if (!inviteCode) {
            errorEl.textContent = '请输入邀请码';
            $('#register-invite').focus();
            return;
        }

        btn.disabled = true;
        btn.textContent = '注册中...';
        errorEl.textContent = '';

        try {
            const response = await fetch('/api/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    username,
                    display_name: displayName,
                    password,
                    invite_code: inviteCode
                }),
            });

            if (!response.ok) {
                let msg = '注册失败';
                try {
                    const data = await response.json();
                    msg = data.detail || msg;
                } catch { /* ignore */ }
                throw new Error(msg);
            }

            $('#login-username').value = username;
            $('#login-password').value = '';
            switchAuthMode('login');
            $('#login-error').style.color = '#3fb950';
            $('#login-error').textContent = '注册成功，请登录';
            setTimeout(() => {
                $('#login-error').style.color = '#f85149';
            }, 3000);
        } catch (err) {
            errorEl.textContent = err.message || '注册失败，请重试';
        } finally {
            btn.disabled = false;
            btn.textContent = '注册';
        }
    }

    /**
     * 检测并转移游客临时下载
     */
    async function checkAndTransferGuestDownloads() {
        if (!isLoggedIn) return;

        try {
            // 获取当前 session 的下载数量
            const countRes = await fetch(`/api/guest-downloads/${guestSessionId}/count?client_id=${encodeURIComponent(clientId)}`);
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
            const token = localStorage.getItem('gotube_admin_token');
            const transferRes = await fetch(`/api/guest-downloads/${guestSessionId}/transfer?client_id=${clientId}`, {
                method: 'POST',
                headers: token ? { 'Authorization': `Bearer ${token}` } : {},
            });

            if (!transferRes.ok) {
                const errData = await transferRes.json();
                throw new Error(errData.detail || '转移失败');
            }

            const transferData = await transferRes.json();
            const transferredCount = transferData.transferred_count;
            const registeredCount = transferData.registered_count || 0;
            const transferErrors = transferData.errors || [];

            // 使用后端返回的 updated_tasks 更新本地任务数据
            if (transferData.updated_tasks && transferData.updated_tasks.length > 0) {
                transferData.updated_tasks.forEach(updatedTask => {
                    if (tasks[updatedTask.task_id]) {
                        storeTask(updatedTask);
                    }
                });
                // 重新渲染任务列表
                renderTasks();
            } else {
                // 如果没有返回 updated_tasks，刷新整个任务列表
                await loadTasks();
            }

            if (registeredCount > 0) {
                const targetText = '视频库';
                showToast(`✅ 已转移 ${transferredCount} 个视频，已保存 ${registeredCount} 个到${targetText}`, '#3fb950');
                rotateGuestSession();
                if (isLibraryUser()) {
                    await loadMyLibrary();
                }
                return;
            }

            if (transferErrors.length > 0) {
                const firstError = transferErrors[0].error || '入库失败';
                showToast(`⚠️ 游客视频未入库：${firstError}`, '#d29922', 5000);
                if (isLibraryUser()) {
                    await loadMyLibrary();
                }
                return;
            }

            showToast(`ℹ️ 没有可转移的视频`, '#8b949e');
            rotateGuestSession();

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
