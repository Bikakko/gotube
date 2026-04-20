/**
 * GoTube Admin - 事件处理模块
 */

function handleKeywordChange(keyword) {
    state.filters.keyword = keyword;
    state.pagination.page = 1;

    clearTimeout(window._searchTimeout);
    window._searchTimeout = setTimeout(() => {
        window.loadVideos();
    }, 300);
}

function handleSourceChange(source) {
    state.filters.source = source;
    state.pagination.page = 1;
    window.loadVideos();
}

function handleTimeChange(time) {
    state.filters.time = time;
    state.pagination.page = 1;
    window.loadVideos();
}

function handleOwnerChange(owner) {
    state.filters.owner = owner;
    state.pagination.page = 1;
    window.loadVideos();
}

function handleOwnerSearchInput(keyword) {
    state.filters.ownerSearchKeyword = keyword;
    window.updateOwnerDropdownOptions();
}

function handlePerPageChange(value) {
    const parsed = Number.parseInt(value, 10);
    if (!Number.isInteger(parsed) || parsed <= 0) return;
    state.pagination.perPage = parsed;
    state.pagination.page = 1;
    window.loadVideos();
}

function toggleVideoSelection(filename, selected) {
    if (selected) {
        state.selectedVideos.add(filename);
    } else {
        state.selectedVideos.delete(filename);
    }
    window.updateSelectAllCheckbox();
    window.updateBatchBar();
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
    window.updateSelectAllCheckbox();
    window.updateBatchBar();
    window.renderVideoGrid();
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
    window.updateSelectAllCheckbox();
    window.updateBatchBar();
    window.renderVideoGrid();
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
        window.switchAdminView('overview');
        window.renderOverviewSection();
        break;
    case 'media':
        await window.showVideoManagement();
        break;
    case 'users':
        await window.showUserManagement();
        break;
    case 'invites':
        await window.showInviteManagement();
        break;
    case 'system':
        document.title = 'GoTube Admin - 系统';
        window.switchAdminView('system');
        window.renderSystemSection();
        if (typeof window.loadSystemPage === 'function') {
            await window.loadSystemPage();
        }
        break;
    default:
        break;
    }
}

function bindAdminShellEvents() {
    const homeLink = $('#admin-home-link');
    if (homeLink) {
        homeLink.addEventListener('click', (e) => {
            e.preventDefault();
            const hiddenPath = window.GOTUBE_HIDDEN_PATH || '7777';
            window.location.href = `/${hiddenPath}`;
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
}

window.handleKeywordChange = handleKeywordChange;
window.handleSourceChange = handleSourceChange;
window.handleTimeChange = handleTimeChange;
window.handleOwnerChange = handleOwnerChange;
window.handleOwnerSearchInput = handleOwnerSearchInput;
window.handlePerPageChange = handlePerPageChange;
window.toggleVideoSelection = toggleVideoSelection;
window.toggleSelectAll = toggleSelectAll;
window.updateSelectAllCheckbox = updateSelectAllCheckbox;
window.clearSelection = clearSelection;
window.toggleDropdown = toggleDropdown;
window.hideAllDropdowns = hideAllDropdowns;
window.bindAdminShellEvents = bindAdminShellEvents;
