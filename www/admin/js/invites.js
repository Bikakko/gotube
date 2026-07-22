/**
 * GoTube Admin - 邀请码管理
 */

import { $, el, apiFetch } from '../../shared/common.module.js';
import { state, invalidateInviteCache } from './state.js';
import { showToast } from './toast.js';
import { closeModal } from './modals.js';
import { switchAdminView } from './users.js';

async function showInviteManagement() {
    if (state.currentUser && state.currentUser.role !== 'admin') {
        showToast('权限不足', 'error');
        return;
    }

    if (state.nav.current === 'invites') {
        await loadInvites(true);
        return;
    }

    document.title = 'GoTube Admin - 邀请码';
    switchAdminView('invites');
    await loadInvites();
}

async function loadInvites(forceReload = false) {
    if (state.invitesLoaded && !forceReload) {
        renderInvitesTable();
        return;
    }

    const slot = $('#invites-table-slot');
    if (slot) {
        slot.innerHTML = '<div class="loading">加载中</div>';
    }

    try {
        const invites = await apiFetch('/invites');
        state.invites = invites;
        state.invitesLoaded = true;
        renderInvitesTable();
    } catch (err) {
        console.error('加载邀请码失败:', err);
        if (slot) {
            slot.innerHTML = `<div class="error">加载失败: ${err.message}</div>`;
        }
    }
}

function getInviteView() {
    return state.inviteView || 'active';
}

function filterInvitesByView(invites) {
    const view = getInviteView();
    if (view === 'archive') {
        return invites.filter((invite) => String(invite.status || '') !== 'active');
    }
    return invites.filter((invite) => String(invite.status || '') === 'active');
}

function getInviteViewSummary(invites) {
    const activeCount = invites.filter((invite) => String(invite.status || '') === 'active').length;
    const archivedCount = invites.length - activeCount;
    return { activeCount, archivedCount };
}

function renderInviteViewTabs(summary) {
    const currentView = getInviteView();
    const tabs = [
        { value: 'active', label: '可用邀请码', count: summary.activeCount },
        { value: 'archive', label: '归档记录', count: summary.archivedCount },
    ];

    return el('div', { className: 'invite-view-tabs' }, tabs.map((tab) => el('button', {
        type: 'button',
        className: `invite-view-tab${currentView === tab.value ? ' active' : ''}`,
        textContent: `${tab.label} ${tab.count}`,
        onClick: () => {
            if (state.inviteView === tab.value) return;
            state.inviteView = tab.value;
            renderInvitesTable();
        },
    })));
}

function renderInvitesTable() {
    const slot = $('#invites-table-slot');
    if (!slot) return;
    const invites = state.invites || [];
    const filteredInvites = filterInvitesByView(invites);
    const summary = getInviteViewSummary(invites);
    const isArchiveView = getInviteView() === 'archive';

    const container = el('div', { className: 'user-table-wrapper invite-table-wrapper' }, [
        el('div', { className: 'admin-section-header' }, [
            el('div', {}, [
                el('h2', { textContent: '邀请码' }),
            ]),
            el('button', {
                className: 'btn btn-primary',
                textContent: '新增邀请码',
                onClick: () => showCreateInviteModal(),
            }),
        ]),
        renderInviteViewTabs(summary),
    ]);

    if (!filteredInvites.length) {
        container.appendChild(el('div', {
            className: 'empty-state empty-state-card',
            textContent: isArchiveView ? '暂无归档邀请码' : '暂无可用邀请码',
        }));
    } else {
        container.appendChild(el('div', { className: 'users-table-shell invite-table-shell' }, [
            el('table', { className: 'users-table' }, [
                el('thead', {}, [
                    el('tr', {}, [
                        el('th', { textContent: 'ID' }),
                        el('th', { textContent: '邀请码' }),
                        el('th', { textContent: '状态' }),
                        el('th', { textContent: '使用次数' }),
                        el('th', { textContent: '配额' }),
                        el('th', { textContent: '过期时间' }),
                        el('th', { textContent: '创建时间' }),
                        el('th', { className: 'invite-actions-head', textContent: '操作' }),
                    ]),
                ]),
                el('tbody', {}, filteredInvites.map((invite) => el('tr', {}, [
                    el('td', { textContent: invite.id }),
                    el('td', { className: 'invite-code-cell' }, renderInviteCodeCell(invite)),
                    el('td', {}, [
                        el('span', {
                            className: `status-badge ${invite.status === 'active' ? 'active' : 'inactive'}`,
                            textContent: formatInviteStatus(invite.status),
                        }),
                    ]),
                    el('td', { textContent: `${invite.used_count || 0} / ${invite.max_uses}` }),
                    el('td', { textContent: invite.storage_quota_mb ? `${invite.storage_quota_mb} MB` : '默认' }),
                    el('td', {
                        textContent: invite.expires_at ? new Date(invite.expires_at).toLocaleString('zh-CN') : '永不过期',
                    }),
                    el('td', {
                        textContent: invite.created_at ? new Date(invite.created_at).toLocaleString('zh-CN') : '-',
                    }),
                    el('td', { className: 'invite-actions-cell' }, [
                        !isArchiveView && invite.is_active
                            ? el('button', {
                                className: 'action-btn-sm danger',
                                textContent: '作废',
                                onClick: () => handleRevokeInvite(invite),
                            })
                            : el('span', { className: 'invite-actions-placeholder', textContent: '—' }),
                    ]),
                ]))),
            ]),
        ]));
    }

    slot.innerHTML = '';
    slot.appendChild(container);
}

function renderInviteCodeCell(invite) {
    if (!invite.code) {
        return [el('span', { className: 'invite-code-placeholder', textContent: '—' })];
    }
    const masked = invite.code.slice(0, 4) + '••••' + invite.code.slice(-4);
    return [
        el('span', { className: 'invite-code-masked', textContent: masked }),
        el('button', {
            className: 'action-btn-sm invite-copy-btn',
            textContent: '📋',
            title: '复制邀请码',
            onClick: () => copyInviteCode(invite.code),
        }),
    ];
}

function formatInviteStatus(status) {
    const map = {
        active: '可用',
        exhausted: '已用完',
        used_up: '已用完',
        expired: '已过期',
        revoked: '已作废',
    };
    return map[status] || status || '未知';
}

function showCreateInviteModal() {
    const overlay = el('div', { className: 'modal active', id: 'invite-create-modal' }, [
        el('div', { className: 'modal-content modal-sm' }, [
            el('div', { className: 'modal-header' }, [
                el('div', { className: 'modal-title', textContent: '新增邀请码' }),
                el('button', {
                    className: 'modal-close',
                    textContent: '×',
                    onClick: () => closeModal('invite-create-modal'),
                }),
            ]),
            el('div', { className: 'modal-body' }, [
                el('div', { className: 'form-group' }, [
                    el('label', { textContent: '最大使用次数' }),
                    el('input', { type: 'number', id: 'invite-max-uses', min: '1', value: '1' }),
                ]),
                el('div', { className: 'form-group' }, [
                    el('label', { textContent: '有效期小时' }),
                    el('input', {
                        type: 'number',
                        id: 'invite-expires-hours',
                        min: '1',
                        placeholder: '留空表示永不过期',
                    }),
                ]),
                el('div', { className: 'form-group' }, [
                    el('label', { textContent: '视频库空间 (MB)' }),
                    el('input', {
                        type: 'number',
                        id: 'invite-storage-quota',
                        min: '1',
                        placeholder: '留空使用默认配额',
                    }),
                ]),
            ]),
            el('div', { className: 'modal-footer' }, [
                el('button', {
                    className: 'btn btn-secondary',
                    textContent: '取消',
                    onClick: () => closeModal('invite-create-modal'),
                }),
                el('button', {
                    className: 'btn btn-primary',
                    textContent: '创建',
                    onClick: () => handleCreateInvite(),
                }),
            ]),
        ]),
    ]);

    document.body.appendChild(overlay);
}

async function handleCreateInvite() {
    const maxUses = Number.parseInt($('#invite-max-uses').value, 10);
    const expiresRaw = $('#invite-expires-hours').value.trim();
    const expiresHours = expiresRaw === '' ? null : Number.parseInt(expiresRaw, 10);
    const quotaRaw = $('#invite-storage-quota').value.trim();
    const storageQuota = quotaRaw === '' ? null : Number.parseInt(quotaRaw, 10);

    if (!Number.isInteger(maxUses) || maxUses < 1) {
        showToast('最大使用次数必须为正整数', 'warning');
        return;
    }

    if (expiresRaw !== '' && (!Number.isInteger(expiresHours) || expiresHours < 1)) {
        showToast('有效期小时必须为空或正整数', 'warning');
        return;
    }

    if (quotaRaw !== '' && (!Number.isInteger(storageQuota) || storageQuota < 1)) {
        showToast('视频库空间必须为空或正整数', 'warning');
        return;
    }

    try {
        const invite = await apiFetch('/invites', {
            method: 'POST',
            body: JSON.stringify({ max_uses: maxUses, expires_hours: expiresHours, storage_quota_mb: storageQuota }),
        });
        invalidateInviteCache();
        await loadInvites(true);
        showInviteCodeModal(invite.code);
    } catch (err) {
        showToast('创建失败: ' + err.message, 'error');
    }
}

function showInviteCodeModal(code) {
    closeModal('invite-create-modal');
    const overlay = el('div', { className: 'modal active', id: 'invite-code-modal' }, [
        el('div', { className: 'modal-content modal-sm' }, [
            el('div', { className: 'modal-header' }, [
                el('div', { className: 'modal-title', textContent: '邀请码已创建' }),
                el('button', {
                    className: 'modal-close',
                    textContent: '×',
                    onClick: () => closeModal('invite-code-modal'),
                }),
            ]),
            el('div', { className: 'modal-body' }, [
                el('p', { className: 'info-text', textContent: '邀请码可在列表中随时查看和复制。' }),
                el('input', { type: 'text', id: 'new-invite-code', value: code || '', readOnly: true }),
            ]),
            el('div', { className: 'modal-footer' }, [
                el('button', {
                    className: 'btn btn-secondary',
                    textContent: '关闭',
                    onClick: () => closeModal('invite-code-modal'),
                }),
                el('button', {
                    className: 'btn btn-primary',
                    textContent: '复制',
                    onClick: () => copyInviteCode(code),
                }),
            ]),
        ]),
    ]);

    document.body.appendChild(overlay);
}

async function copyInviteCode(code) {
    try {
        await navigator.clipboard.writeText(code || '');
        showToast('已复制', 'success');
    } catch (err) {
        showToast('复制失败，请手动复制', 'warning');
    }
}

async function handleRevokeInvite(invite) {
    if (!confirm(`确定作废邀请码 #${invite.id} 吗？`)) return;

    try {
        await apiFetch(`/invites/${invite.id}`, { method: 'DELETE' });
        invalidateInviteCache();
        await loadInvites(true);
        showToast('邀请码已作废', 'success');
    } catch (err) {
        showToast('作废失败: ' + err.message, 'error');
    }
}

export { showInviteManagement, loadInvites, renderInvitesTable };
