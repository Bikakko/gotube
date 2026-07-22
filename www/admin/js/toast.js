/**
 * GoTube Admin - Toast 提示系统
 * 显示成功、错误、警告、信息提示
 */

import { $, el } from '../../shared/common.module.js';

/**
 * 显示 Toast 提示
 * @param {string} message - 提示内容
 * @param {string} type - 类型: success/error/warning/info
 * @param {number} duration - 显示时长（毫秒），默认 3000
 */
function showToast(message, type = 'info', duration = 3000) {
    // 创建 container（如果不存在）
    let container = $('.toast-container');
    if (!container) {
        container = el('div', { className: 'toast-container', id: 'toast-container' });
        document.body.appendChild(container);
    }

    // 创建 toast 元素
    const toast = el('div', {
        className: `toast ${type}`,
        textContent: message,
    });

    container.appendChild(toast);

    // 自动移除
    setTimeout(() => {
        toast.classList.add('removing');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

export { showToast };
