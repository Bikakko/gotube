/**
 * GoTube Admin - Cookie 管理模块
 * 提供上传、查看状态、删除 cookies 的功能
 */

// ========== Cookie 管理界面 ==========

/**
 * 显示 Cookie 管理模态框
 */
function showCookiesManagement() {
    // 关闭其他下拉菜单
    hideAllDropdowns();

    // 创建模态框
    const modal = el('div', { className: 'modal active', id: 'cookies-modal' }, [
        el('div', { className: 'modal-content', style: 'max-width: 600px;' }, [
            // 头部
            el('div', { className: 'modal-header' }, [
                el('div', { className: 'modal-title', textContent: '🍪 Cookie 管理' }),
                el('button', {
                    className: 'modal-close',
                    textContent: '×',
                    onClick: () => modal.remove(),
                }),
            ]),
            // 内容
            el('div', { className: 'modal-body', id: 'cookies-modal-body' }, [
                // 状态卡片
                el('div', { id: 'cookies-status-card', style: 'margin-bottom: 20px;' }),
                // 上传区域
                el('div', { id: 'cookies-upload-area' }),
            ]),
            // 底部
            el('div', { className: 'modal-footer' }, [
                el('button', {
                    className: 'btn btn-secondary',
                    textContent: '关闭',
                    onClick: () => modal.remove(),
                }),
            ]),
        ]),
    ]);

    document.body.appendChild(modal);

    // 加载状态
    loadCookiesStatus();
    
    // 渲染上传区域
    renderUploadArea();
}

/**
 * 加载 cookies 状态
 */
async function loadCookiesStatus() {
    const container = $('#cookies-status-card');
    if (!container) return;

    const token = localStorage.getItem('gotube_admin_token');
    if (!token) {
        container.innerHTML = `
            <div style="padding: 15px; background: rgba(244, 67, 54, 0.1); border-radius: 8px; color: var(--error);">
                ⚠️ 未登录，请先登录
            </div>
        `;
        return;
    }

    try {
        const response = await fetch(`/${GOTUBE_HIDDEN_PATH}/admin/api/cookies/status`, {
            headers: {
                'Authorization': `Bearer ${token}`,
            },
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        renderCookiesStatus(container, data);
    } catch (error) {
        console.error('加载 cookies 状态失败:', error);
        container.innerHTML = `
            <div style="padding: 15px; background: rgba(244, 67, 54, 0.1); border-radius: 8px; color: var(--error);">
                ⚠️ 加载状态失败: ${error.message}
            </div>
        `;
    }
}

/**
 * 渲染 cookies 状态
 */
function renderCookiesStatus(container, data) {
    if (!data.has_cookies) {
        container.innerHTML = `
            <div style="padding: 20px; background: var(--surface); border-radius: 8px; text-align: center;">
                <div style="font-size: 48px; margin-bottom: 10px;">🍪</div>
                <div style="font-size: 16px; font-weight: bold; margin-bottom: 8px;">未配置 Cookies</div>
                <div style="font-size: 14px; color: var(--text-sec);">
                    请上传 cookies.txt 文件以支持需要登录的视频网站下载
                </div>
            </div>
        `;
        return;
    }

    const sourceText = data.source === 'upload' ? '网页上传' : '.env 配置';
    const domainsHtml = data.domains && data.domains.length > 0
        ? `
            <div style="margin-top: 15px;">
                <div style="font-size: 13px; color: var(--text-sec); margin-bottom: 8px;">
                    包含域名 (${data.domain_count} 个):
                </div>
                <div style="display: flex; flex-wrap: wrap; gap: 6px;">
                    ${data.domains.slice(0, 20).map(d =>
                        `<span style="padding: 4px 10px; background: rgba(33, 150, 243, 0.15); border-radius: 12px; font-size: 12px; color: var(--info);">${d}</span>`
                    ).join('')}
                    ${data.domains.length > 20 ? `<span style="padding: 4px 10px; color: var(--text-sec); font-size: 12px;">+${data.domains.length - 20} 更多</span>` : ''}
                </div>
            </div>
        `
        : '';

    container.innerHTML = `
        <div style="padding: 20px; background: var(--surface); border-radius: 8px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                <div style="font-size: 16px; font-weight: bold; color: var(--success);">✅ 已配置 Cookies</div>
                ${data.source === 'upload' ? `
                    <button class="btn btn-danger" style="padding: 6px 12px; font-size: 13px;" onclick="deleteCookies()">
                        🗑️ 删除上传的 cookies
                    </button>
                ` : ''}
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 15px; margin-bottom: 15px;">
                <div>
                    <div style="font-size: 12px; color: var(--text-sec); margin-bottom: 4px;">文件大小</div>
                    <div style="font-size: 18px; font-weight: bold;">${data.file_size_human}</div>
                </div>
                <div>
                    <div style="font-size: 12px; color: var(--text-sec); margin-bottom: 4px;">更新时间</div>
                    <div style="font-size: 14px;">${formatDateTime(data.modified_time)}</div>
                </div>
                <div>
                    <div style="font-size: 12px; color: var(--text-sec); margin-bottom: 4px;">来源</div>
                    <div style="font-size: 14px;">${sourceText}</div>
                </div>
                <div>
                    <div style="font-size: 12px; color: var(--text-sec); margin-bottom: 4px;">域名数量</div>
                    <div style="font-size: 18px; font-weight: bold;">${data.domain_count}</div>
                </div>
            </div>
            ${domainsHtml}
        </div>
    `;
}

/**
 * 格式化日期时间
 */
function formatDateTime(isoString) {
    if (!isoString) return '未知';
    try {
        const date = new Date(isoString);
        return date.toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
        });
    } catch (e) {
        return isoString;
    }
}

/**
 * 渲染上传区域
 */
function renderUploadArea() {
    const container = $('#cookies-upload-area');
    if (!container) return;

    container.innerHTML = `
        <div style="padding: 20px; background: var(--surface); border-radius: 8px;">
            <div style="font-size: 16px; font-weight: bold; margin-bottom: 15px;">📤 上传/更新 Cookies</div>
            
            <!-- 文件上传 -->
            <div style="margin-bottom: 20px;">
                <label style="display: block; margin-bottom: 8px; font-size: 14px; color: var(--text-sec);">
                    方式一：上传 cookies.txt 文件
                </label>
                <div style="display: flex; gap: 10px; align-items: center;">
                    <input type="file" id="cookies-file-input" accept=".txt" style="flex: 1; padding: 10px; border: 1px solid var(--border); background: var(--bg); color: var(--text); border-radius: 4px;">
                    <button class="btn btn-primary" onclick="uploadCookiesFile()" style="white-space: nowrap;">
                        上传文件
                    </button>
                </div>
            </div>

            <!-- 文本输入 -->
            <div style="margin-bottom: 20px;">
                <label style="display: block; margin-bottom: 8px; font-size: 14px; color: var(--text-sec);">
                    方式二：粘贴 cookies 文本内容（Netscape 格式）
                </label>
                <textarea id="cookies-text-input" rows="8" style="width: 100%; padding: 10px; border: 1px solid var(--border); background: var(--bg); color: var(--text); border-radius: 4px; font-family: monospace; font-size: 12px; resize: vertical;" placeholder="# Netscape HTTP Cookie File&#10;youtube.com	TRUE	/	FALSE	...	__Secure-1PSID	xxx&#10;..."></textarea>
                <button class="btn btn-primary" onclick="uploadCookiesText()" style="margin-top: 10px; width: 100%;">
                    提交文本
                </button>
            </div>

            <!-- 说明 -->
            <div style="padding: 15px; background: rgba(255, 152, 0, 0.1); border-radius: 6px; border-left: 3px solid var(--warning);">
                <div style="font-size: 14px; font-weight: bold; margin-bottom: 8px; color: var(--warning);">⚠️ 注意事项</div>
                <ul style="font-size: 13px; color: var(--text-sec); margin-left: 20px; line-height: 1.8;">
                    <li>Cookies 文件应为 Netscape 格式（从浏览器插件导出）</li>
                    <li>一个文件可包含多个网站的 cookies，yt-dlp 会自动匹配对应域名</li>
                    <li>上传后会自动热重载，无需重启服务</li>
                    <li>旧 cookies 文件会自动备份到 data 目录</li>
                    <li>文件大小限制：最大 1MB</li>
                </ul>
            </div>
        </div>
    `;
}

/**
 * 上传 cookies 文件
 */
async function uploadCookiesFile() {
    const fileInput = $('#cookies-file-input');
    if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
        showToast('请选择 cookies.txt 文件', 'warning');
        return;
    }

    const file = fileInput.files[0];
    if (!file.name.endsWith('.txt')) {
        showToast('仅支持 .txt 格式文件', 'error');
        return;
    }

    if (file.size > 1024 * 1024) {
        showToast('文件过大（最大 1MB）', 'error');
        return;
    }

    const token = localStorage.getItem('gotube_admin_token');
    if (!token) {
        showToast('请先登录', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
        showToast('正在上传 cookies...', 'info');

        const response = await fetch(`/${GOTUBE_HIDDEN_PATH}/admin/api/cookies/upload`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
            },
            body: formData,
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || '上传失败');
        }

        showToast(`✅ ${data.message}\n包含 ${data.domain_count} 个域名`, 'success');
        
        // 刷新状态
        await loadCookiesStatus();
    } catch (error) {
        console.error('上传 cookies 失败:', error);
        showToast(`❌ 上传失败: ${error.message}`, 'error');
    }
}

/**
 * 上传 cookies 文本
 */
async function uploadCookiesText() {
    const textarea = $('#cookies-text-input');
    if (!textarea || !textarea.value.trim()) {
        showToast('请输入 cookies 文本内容', 'warning');
        return;
    }

    const token = localStorage.getItem('gotube_admin_token');
    if (!token) {
        showToast('请先登录', 'error');
        return;
    }

    const content = textarea.value.trim();

    try {
        showToast('正在提交 cookies...', 'info');

        const response = await fetch(`/${GOTUBE_HIDDEN_PATH}/admin/api/cookies/upload`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ content }),
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || '提交失败');
        }

        showToast(`✅ ${data.message}\n包含 ${data.domain_count} 个域名`, 'success');
        
        // 清空输入框
        textarea.value = '';
        
        // 刷新状态
        await loadCookiesStatus();
    } catch (error) {
        console.error('提交 cookies 失败:', error);
        showToast(`❌ 提交失败: ${error.message}`, 'error');
    }
}

/**
 * 删除上传的 cookies
 */
async function deleteCookies() {
    if (!confirm('确定要删除上传的 cookies 文件吗？\n\n删除后会恢复到 .env 配置的路径。')) {
        return;
    }

    const token = localStorage.getItem('gotube_admin_token');
    if (!token) {
        showToast('请先登录', 'error');
        return;
    }

    try {
        showToast('正在删除 cookies...', 'info');

        const response = await fetch(`/${GOTUBE_HIDDEN_PATH}/admin/api/cookies`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`,
            },
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || '删除失败');
        }

        showToast(`✅ ${data.message}`, 'success');
        
        // 刷新状态
        await loadCookiesStatus();
    } catch (error) {
        console.error('删除 cookies 失败:', error);
        showToast(`❌ 删除失败: ${error.message}`, 'error');
    }
}

// ========== 导出到全局 ==========
window.showCookiesManagement = showCookiesManagement;
window.loadCookiesStatus = loadCookiesStatus;
window.uploadCookiesFile = uploadCookiesFile;
window.uploadCookiesText = uploadCookiesText;
window.deleteCookies = deleteCookies;
