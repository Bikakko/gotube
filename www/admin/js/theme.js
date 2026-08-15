/**
 * GoTube Admin - 主题切换模块
 *
 * 柔光玻璃双主题：
 *   - dark  : 夜幕玻璃（默认）
 *   - light : 晨雾玻璃
 * 选择持久化到 localStorage('gotube_admin_theme')；
 * 首屏由 index.html 内联引导脚本在样式加载前应用，避免闪烁。
 */

const STORAGE_KEY = 'gotube_admin_theme';

function currentTheme() {
    return document.documentElement.dataset.theme === 'light' ? 'light' : 'dark';
}

function updateToggleButton() {
    const icon = document.getElementById('admin-theme-icon');
    const btn = document.getElementById('admin-theme-toggle');
    if (!icon || !btn) return;
    const theme = currentTheme();
    icon.textContent = theme === 'dark' ? '☾' : '☀';
    btn.title = theme === 'dark' ? '切换到晨雾玻璃（浅色）' : '切换到夜幕玻璃（深色）';
}

function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    try {
        localStorage.setItem(STORAGE_KEY, theme);
    } catch (e) {
        // 存储不可用时仅在当前会话生效
    }
    updateToggleButton();
}

function toggleTheme() {
    applyTheme(currentTheme() === 'dark' ? 'light' : 'dark');
}

function initThemeToggle() {
    const btn = document.getElementById('admin-theme-toggle');
    if (!btn) return;
    btn.addEventListener('click', toggleTheme);
    updateToggleButton();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initThemeToggle);
} else {
    initThemeToggle();
}

export { currentTheme, applyTheme, toggleTheme, initThemeToggle };
