/**
 * GoTube - 全局兼容层
 *
 * 将统一共享模块（common.module.js）的工具挂到 window，
 * 供仍使用全局脚本写法的页面以裸全局方式调用：
 * - admin 各业务文件（window.xxx 导出 + 裸全局调用 $ / el / apiFetch 等）
 * - watch 页内联脚本（window.GoTube.attachVideoKeyboardControls）
 *
 * 注意：本文件必须以 ES Module 方式加载（<script type="module">），
 * 且需先于业务脚本执行，window 才会被填充。
 */
import {
    $,
    $$,
    el,
    formatBytes,
    formatSpeed,
    formatETA,
    escapeHtml,
    extractSource,
    formatRole,
    getApiBase,
    apiFetch,
    attachVideoKeyboardControls,
    resolveHiddenPath,
    session,
} from './common.module.js';

// 裸全局工具函数（admin 文件以 $、el、apiFetch 等裸标识符调用）
window.$ = $;
window.$$ = $$;
window.el = el;
window.formatBytes = formatBytes;
window.formatSpeed = formatSpeed;
window.formatETA = formatETA;
window.escapeHtml = escapeHtml;
window.extractSource = extractSource;
window.formatRole = formatRole;
window.getApiBase = getApiBase;
window.apiFetch = apiFetch;

// 会话对象与 GoTube 命名空间（兼容 common.js 时代的全局对象）
window.GoTubeSession = session;
window.GoTube = window.GoTube || {};
window.GoTube.session = session;
window.GoTube.resolveHiddenPath = resolveHiddenPath;
window.GoTube.attachVideoKeyboardControls = attachVideoKeyboardControls;
window.GoTube.utils = {
    $,
    $$,
    el,
    formatBytes,
    formatSpeed,
    formatETA,
    escapeHtml,
    extractSource,
    formatRole,
    getApiBase,
    apiFetch,
};
