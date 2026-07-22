/**
 * GoTube Admin - Cookie 管理模块
 * 提供上传、查看状态、删除 cookies 的功能
 */

import { $, el } from '../../shared/common.module.js';
import { showToast } from './toast.js';
import { loadSystemPage } from './system.js';

// ========== Cookie 管理界面 ==========

/**
 * 显示 Cookie 管理模态框
 */
function showCookiesManagement() {
    // 创建模态框
    const modal = el('div', { className: 'modal active', id: 'cookies-modal' }, [
        el('div', { className: 'modal-content', style: 'max-width: 600px;' }, [
            // 头部
            el('div', { className: 'modal-header' }, [
                el('div', { className: 'modal-title', textContent: '上传或更新 Cookie' }),
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
        renderCookiesStatus(container, data, { context: 'modal' });
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
const COOKIE_PLATFORM_LABELS = {
    bilibili: 'Bilibili',
    twitter: 'X/Twitter',
    youtube: 'YouTube',
};

function escapeCookieHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (ch) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
    }[ch]));
}

function renderCookieDiagnostics(data) {
    const diagnostics = data.diagnostics || {};
    const platforms = Object.keys(COOKIE_PLATFORM_LABELS);

    return `
        <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid var(--border);">
            <div style="font-size: 13px; color: var(--text-sec); margin-bottom: 10px;">平台登录态诊断</div>
            <div style="display: grid; gap: 10px;">
                ${platforms.map((platform) => {
                    const item = diagnostics[platform] || {};
                    const hasRequired = Boolean(item.has_required);
                    const present = Array.isArray(item.present) ? item.present : [];
                    const missing = Array.isArray(item.missing) ? item.missing : [];
                    const domains = Array.isArray(item.domains) ? item.domains : [];
                    return `
                        <div style="padding: 10px; background: var(--bg); border: 1px solid var(--border); border-radius: 8px;">
                            <div style="display: flex; justify-content: space-between; gap: 10px; align-items: center;">
                                <strong>${escapeCookieHtml(COOKIE_PLATFORM_LABELS[platform])}</strong>
                                <span style="color: ${hasRequired ? 'var(--success)' : 'var(--warning)'};">
                                    ${hasRequired ? '完整' : '缺字段'}
                                </span>
                            </div>
                            <div style="margin-top: 6px; font-size: 12px; color: var(--text-sec); line-height: 1.6;">
                                已有：${present.length ? present.map(escapeCookieHtml).join(', ') : '无'}
                                <br>
                                缺少：${missing.length ? missing.map(escapeCookieHtml).join(', ') : '无'}
                                ${domains.length ? `<br>域名：${domains.slice(0, 6).map(escapeCookieHtml).join(', ')}${domains.length > 6 ? ` 等 ${domains.length} 个` : ''}` : ''}
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>
        </div>
    `;
}

function renderCookiePlatformSummary(data) {
    const diagnostics = data.diagnostics || {};
    const platforms = Object.entries(COOKIE_PLATFORM_LABELS);

    return `
        <div class="cookie-platform-list">
            ${platforms.map(([platform, label]) => {
                const item = diagnostics[platform] || {};
                const ready = Boolean(item.has_required);
                return `
                    <div class="cookie-platform-item ${ready ? 'ready' : 'missing'}">
                        <span class="cookie-platform-name">${escapeCookieHtml(label)}</span>
                        <span class="cookie-platform-state">${ready ? '可用' : '未配置'}</span>
                    </div>
                `;
            }).join('')}
        </div>
    `;
}

function renderCookiesStatus(container, data, options = {}) {
    const context = options.context || 'modal';
    if (!data.has_cookies) {
        container.innerHTML = `
            <div class="cookie-status-panel empty">
                <div class="cookie-status-main">
                    <div class="cookie-status-heading">未配置 Cookie</div>
                    <p class="cookie-status-copy">上传 cookies.txt 文件后，系统会立即更新当前运行时 Cookie。</p>
                </div>
                <div class="cookie-status-metrics">
                    <div class="cookie-metric-card">
                        <div class="cookie-metric-label">来源</div>
                        <div class="cookie-metric-value">未配置</div>
                    </div>
                    <div class="cookie-metric-card">
                        <div class="cookie-metric-label">域名数量</div>
                        <div class="cookie-metric-value">0</div>
                    </div>
                </div>
            </div>
        `;
        return;
    }

    const sourceTextMap = {
        upload: '网页上传',
        env_import: '.env 首次导入',
        none: '未配置',
    };
    const sourceText = sourceTextMap[data.source] || '未知来源';
    const domainsHtml = data.domains && data.domains.length > 0
        ? `
            <div class="cookie-domains-block">
                <div class="cookie-block-label">已识别域名</div>
                <div class="cookie-domain-list">
                    ${data.domains.slice(0, 20).map((domain) =>
                        `<span class="cookie-domain-chip">${escapeCookieHtml(domain)}</span>`
                    ).join('')}
                    ${data.domains.length > 20 ? `<span class="cookie-domain-more">+${data.domains.length - 20} 个</span>` : ''}
                </div>
            </div>
        `
        : '';
    const diagnosticsHtml = `
        <details class="cookie-diagnostics" ${context === 'system' ? '' : 'open'}>
            <summary>查看平台诊断</summary>
            ${renderCookieDiagnostics(data)}
        </details>
    `;

    container.innerHTML = `
        <div class="cookie-status-panel">
            <div class="cookie-status-main">
                <div class="cookie-status-heading">当前运行时 Cookie 已生效</div>
                <p class="cookie-status-copy">后续上传会按域名与 Cookie 键进行合并，未匹配的现有记录会保留。</p>
                ${renderCookiePlatformSummary(data)}
            </div>
            <div class="cookie-status-metrics">
                <div class="cookie-metric-card">
                    <div class="cookie-metric-label">来源</div>
                    <div class="cookie-metric-value">${sourceText}</div>
                </div>
                <div class="cookie-metric-card">
                    <div class="cookie-metric-label">更新时间</div>
                    <div class="cookie-metric-value cookie-metric-value-sm">${formatDateTime(data.modified_time)}</div>
                </div>
                <div class="cookie-metric-card">
                    <div class="cookie-metric-label">文件大小</div>
                    <div class="cookie-metric-value">${data.file_size_human}</div>
                </div>
                <div class="cookie-metric-card">
                    <div class="cookie-metric-label">域名数量</div>
                    <div class="cookie-metric-value">${data.domain_count}</div>
                </div>
            </div>
            ${domainsHtml}
            ${diagnosticsHtml}
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
        <div class="cookie-upload-panel">
            <div class="cookie-upload-heading">上传或更新 Cookie</div>
            
            <div class="cookie-upload-note">
                <div class="cookie-upload-note-title">智能合并模式</div>
                <div class="cookie-upload-note-copy">
                    上传新 Cookie 时，只会覆盖匹配的 Cookie 记录，不会清空其他平台的现有配置。
                </div>
            </div>
            
            <div class="cookie-upload-section">
                <label class="cookie-upload-label">
                    方式一：上传 cookies.txt 文件
                </label>
                <div class="cookie-upload-row">
                    <input type="file" id="cookies-file-input" accept=".txt" class="cookie-upload-input">
                    <button class="btn btn-primary" data-action="upload-cookies-file" style="white-space: nowrap;">
                        上传文件
                    </button>
                </div>
            </div>

            <div class="cookie-upload-section">
                <label class="cookie-upload-label">
                    方式二：粘贴 cookies 文本内容（Netscape 格式）
                </label>
                <textarea id="cookies-text-input" rows="8" class="cookie-upload-textarea" placeholder="# Netscape HTTP Cookie File&#10;youtube.com	TRUE	/	FALSE	...	__Secure-1PSID	xxx&#10;..."></textarea>
                <button class="btn btn-primary cookie-upload-submit" data-action="upload-cookies-text">
                    提交文本
                </button>
            </div>

            <div class="cookie-upload-tips">
                <div class="cookie-upload-note-title">注意事项</div>
                <ul class="cookie-upload-list">
                    <li>Cookies 文件应为 Netscape 格式（从浏览器插件导出）</li>
                    <li>智能合并会按 Cookie 键覆盖，不影响其他平台</li>
                    <li>上传前会显示确认对话框，列出将影响的域名</li>
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

    try {
        // 先读取文件内容用于预检查
        const content = await readFileAsText(file);
        if (!content.trim()) {
            showToast('文件内容为空', 'warning');
            return;
        }

        showToast('正在检查 cookies...', 'info');

        // 预检查
        const checkResponse = await fetch(`/${GOTUBE_HIDDEN_PATH}/admin/api/cookies/check_merge`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ content }),
        });

        const checkData = await checkResponse.json();

        if (!checkResponse.ok) {
            throw new Error(checkData.detail || '预检查失败');
        }

        // 显示确认对话框
        const confirmed = await showMergeConfirmDialog(checkData);
        if (!confirmed) {
            showToast('已取消上传', 'info');
            return;
        }

        // 用户确认，执行上传
        showToast('正在上传 cookies...', 'info');

        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`/${GOTUBE_HIDDEN_PATH}/admin/api/cookies/upload?mode=merge`, {
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

        showToast(`✅ ${data.message}\n当前共 ${data.domain_count} 个域名`, 'success');
        
        // 刷新状态
        await loadCookiesStatus();
        await loadSystemPage(true);
    } catch (error) {
        console.error('上传 cookies 失败:', error);
        showToast(`❌ 上传失败: ${error.message}`, 'error');
    }
}

/**
 * 读取文件为文本
 */
function readFileAsText(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => resolve(e.target.result);
        reader.onerror = (e) => reject(new Error('读取文件失败'));
        reader.readAsText(file);
    });
}

/**
 * 显示智能合并确认对话框
 */
function showMergeConfirmDialog(checkData) {
    return new Promise((resolve) => {
        const {
            will_replace,
            will_add,
            replace_count,
            add_count,
            unchanged_domains,
            will_replace_cookie_count = 0,
            will_add_cookie_count = 0,
            will_preserve_cookie_count = 0,
            replace_cookie_samples = [],
            add_cookie_samples = [],
        } = checkData;

        let message = '📋 上传确认\n\n';
        
        if (replace_count > 0) {
            message += `🔄 将替换 ${replace_count} 个域名：\n`;
            message += will_replace.join(', ') + '\n\n';
        }

        if (will_replace_cookie_count > 0) {
            message += `🔁 将覆盖 ${will_replace_cookie_count} 条 Cookie 记录`;
            if (replace_cookie_samples.length > 0) {
                message += `（例如：${replace_cookie_samples.join('；')}）`;
            }
            message += '\n\n';
        }
        
        if (add_count > 0) {
            message += `➕ 将新增 ${add_count} 个域名：\n`;
            message += will_add.join(', ') + '\n\n';
        }

        if (will_add_cookie_count > 0) {
            message += `🆕 将新增 ${will_add_cookie_count} 条 Cookie 记录`;
            if (add_cookie_samples.length > 0) {
                message += `（例如：${add_cookie_samples.join('；')}）`;
            }
            message += '\n\n';
        }

        if (will_preserve_cookie_count > 0) {
            message += `✅ 将保留 ${will_preserve_cookie_count} 条现有 Cookie 记录\n\n`;
        }
        
        if (unchanged_domains.length > 0) {
            message += `✅ 不影响 ${unchanged_domains.length} 个域名：\n`;
            message += unchanged_domains.slice(0, 10).join(', ');
            if (unchanged_domains.length > 10) {
                message += ` 等${unchanged_domains.length}个`;
            }
            message += '\n\n';
        }

        message += '是否继续？';

        const confirmed = confirm(message);
        resolve(confirmed);
    });
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
        showToast('正在检查 cookies...', 'info');

        // 预检查
        const checkResponse = await fetch(`/${GOTUBE_HIDDEN_PATH}/admin/api/cookies/check_merge`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ content }),
        });

        const checkData = await checkResponse.json();

        if (!checkResponse.ok) {
            throw new Error(checkData.detail || '预检查失败');
        }

        // 显示确认对话框
        const confirmed = await showMergeConfirmDialog(checkData);
        if (!confirmed) {
            showToast('已取消提交', 'info');
            return;
        }

        // 用户确认，执行提交
        showToast('正在提交 cookies...', 'info');

        const response = await fetch(`/${GOTUBE_HIDDEN_PATH}/admin/api/cookies/upload?mode=merge`, {
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

        showToast(`✅ ${data.message}\n当前共 ${data.domain_count} 个域名`, 'success');
        
        // 清空输入框
        textarea.value = '';
        
        // 刷新状态
        await loadCookiesStatus();
        await loadSystemPage(true);
    } catch (error) {
        console.error('提交 cookies 失败:', error);
        showToast(`❌ 提交失败: ${error.message}`, 'error');
    }
}

/**
 * 删除上传的 cookies
 */
async function deleteCookies() {
    if (!confirm('确定要删除上传的 cookies 文件吗？\n\n删除后下载器将停止使用 Cookie，不会自动回退到根目录 cookies.txt。')) {
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
        await loadSystemPage(true);
    } catch (error) {
        console.error('删除 cookies 失败:', error);
        showToast(`❌ 删除失败: ${error.message}`, 'error');
    }
}

export { showCookiesManagement, loadCookiesStatus, uploadCookiesFile, uploadCookiesText, deleteCookies, renderCookiesStatus };
