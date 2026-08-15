/**
 * GoTube Admin - 事件处理模块
 */

import { $ } from '../../shared/common.module.js';
import { state } from './state.js';
import { loadVideos } from './data.js';
import { updateOwnerDropdownOptions, updateBatchBar, renderOverviewSection, renderSystemSection, setCustomDropdownValue, hideAllCustomDropdowns } from './render.js';
import { switchAdminView, showVideoManagement, showUserManagement } from './users.js';
import { showInviteManagement } from './invites.js';
import { loadSystemPage } from './system.js';
import { uploadCookiesFile, uploadCookiesText } from './cookies.js';

function handleKeywordChange(keyword) {
    state.filters.keyword = keyword;
    state.pagination.page = 1;

    clearTimeout(window._searchTimeout);
    window._searchTimeout = setTimeout(() => {
        loadVideos();
    }, 300);
}

function handleSourceChange(source) {
    state.filters.source = source;
    state.pagination.page = 1;
    loadVideos();
}

function handleTimeChange(time) {
    state.filters.time = time;
    state.pagination.page = 1;
    loadVideos();
}

function handleOwnerChange(owner) {
    state.filters.owner = owner;
    state.pagination.page = 1;
    loadVideos();
}

function handleOwnerSearchInput(keyword) {
    state.filters.ownerSearchKeyword = keyword;
    updateOwnerDropdownOptions();
}

function handlePerPageChange(value) {
    const parsed = Number.parseInt(value, 10);
    if (!Number.isInteger(parsed) || parsed <= 0) return;
    state.pagination.perPage = parsed;
    state.pagination.page = 1;
    loadVideos();
}

function toggleVideoSelection(filename, selected) {
    if (selected) {
        state.selectedVideos.add(filename);
    } else {
        state.selectedVideos.delete(filename);
    }
    updateSelectAllCheckbox();
    updateBatchBar();
}

/**
 * 就地同步所有卡片的"选择"按钮样式。
 * 性能优化：全选/清空只改按钮文案与 class，不再销毁重建整个视频网格。
 */
function syncVideoSelectToggles() {
    document.querySelectorAll('.video-select-toggle').forEach((btn) => {
        const selected = state.selectedVideos.has(btn.dataset.filename);
        btn.textContent = selected ? '已选中' : '选择';
        btn.classList.toggle('selected', selected);
    });
}

function toggleSelectAll(selectAll) {
    if (selectAll) {
        state.filteredVideos.forEach(video => {
            state.selectedVideos.add(video.filename);
        });
    } else {
        state.filteredVideos.forEach(video => {
            state.selectedVideos.delete(video.filename);
        });
    }
    updateSelectAllCheckbox();
    updateBatchBar();
    syncVideoSelectToggles();
}

function updateSelectAllCheckbox() {
    const checkbox = $('#select-all-checkbox');
    if (!checkbox) return;

    const totalVideos = state.filteredVideos.length;
    const selectedCount = state.selectedVideos.size;

    if (totalVideos === 0) {
        checkbox.checked = false;
        checkbox.indeterminate = false;
    } else if (selectedCount === 0) {
        checkbox.checked = false;
        checkbox.indeterminate = false;
    } else if (selectedCount >= totalVideos) {
        checkbox.checked = true;
        checkbox.indeterminate = false;
    } else {
        checkbox.checked = false;
        checkbox.indeterminate = true;
    }
}

function clearSelection() {
    state.selectedVideos.clear();
    updateSelectAllCheckbox();
    updateBatchBar();
    syncVideoSelectToggles();
}

function toggleDropdown(menuId) {
    const menu = $(`#${menuId}`);
    if (!menu) return;

    const isOpen = menu.classList.contains('show');
    hideAllDropdowns();
    if (!isOpen) {
        menu.classList.add('show');
    }
}

function hideAllDropdowns() {
    document.querySelectorAll('.dropdown-menu.show').forEach(menu => {
        menu.classList.remove('show');
    });
}

async function handleAdminNav(view) {
    switch (view) {
    case 'overview':
        document.title = 'GoTube Admin - 概览';
        switchAdminView('overview');
        renderOverviewSection();
        break;
    case 'media':
        await showVideoManagement();
        break;
    case 'users':
        await showUserManagement();
        break;
    case 'invites':
        await showInviteManagement();
        break;
    case 'system':
        document.title = 'GoTube Admin - 系统';
        switchAdminView('system');
        renderSystemSection();
        await loadSystemPage();
        break;
    default:
        break;
    }
}

function bindAdminShellEvents() {
    const deriveHiddenPath = () => {
        const parts = window.location.pathname.split('/').filter(Boolean);
        return parts[0] || '';
    };

    const homeLink = $('#admin-home-link');
    if (homeLink) {
        homeLink.addEventListener('click', (e) => {
            e.preventDefault();
            const hiddenPath = window.GOTUBE_HIDDEN_PATH || deriveHiddenPath();
            if (hiddenPath) {
                window.location.href = `/${hiddenPath}`;
            }
        });
    }

    document.querySelectorAll('[data-admin-nav]').forEach(button => {
        button.addEventListener('click', async () => {
            await handleAdminNav(button.dataset.adminNav);
        });
    });

    if (!window._adminShellDocumentClickBound) {
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.dropdown')) {
                hideAllDropdowns();
            }
        });
        window._adminShellDocumentClickBound = true;
    }

    // 事件委托：统一处理由 render.js 通过 data-action 标记的交互
    document.addEventListener('click', (e) => {
        const target = e.target.closest('[data-action]');
        if (!target) return;
        const action = target.dataset.action;

        if (action === 'filter-change') {
            e.stopPropagation();
            const filterType = target.dataset.filterType;
            const value = target.dataset.value;
            const text = target.textContent;
            if (filterType === 'source') {
                handleSourceChange(value);
                setCustomDropdownValue('source-dropdown', value, text);
            } else if (filterType === 'time') {
                handleTimeChange(value);
                setCustomDropdownValue('time-dropdown', value, text);
            } else if (filterType === 'owner') {
                handleOwnerChange(value);
                setCustomDropdownValue('owner-dropdown', value, text);
            }
            hideAllCustomDropdowns();
        } else if (action === 'toggle-select') {
            const filename = target.dataset.filename;
            const isCurrentlySelected = state.selectedVideos.has(filename);
            const newState = !isCurrentlySelected;
            toggleVideoSelection(filename, newState);
            target.textContent = newState ? '已选中' : '选择';
            target.classList.toggle('selected', newState);
        } else if (action === 'upload-cookies-file') {
            uploadCookiesFile();
        } else if (action === 'upload-cookies-text') {
            uploadCookiesText();
        }
    });

    document.addEventListener('input', (e) => {
        const action = e.target.dataset.action;
        if (action === 'search-input') {
            handleKeywordChange(e.target.value);
        } else if (action === 'owner-search-input') {
            handleOwnerSearchInput(e.target.value);
        }
    });

    document.addEventListener('change', (e) => {
        const action = e.target.dataset.action;
        if (action === 'select-all') {
            toggleSelectAll(e.target.checked);
        } else if (action === 'per-page-change') {
            handlePerPageChange(e.target.value);
        }
    });
}

export { handleKeywordChange, handleSourceChange, handleTimeChange, handleOwnerChange, handleOwnerSearchInput, handlePerPageChange, toggleVideoSelection, toggleSelectAll, updateSelectAllCheckbox, clearSelection, toggleDropdown, hideAllDropdowns, bindAdminShellEvents };
