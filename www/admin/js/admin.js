/**
 * GoTube Admin - application bootstrap
 */

import { checkAuth } from './auth.js';
import { renderPage } from './render.js';
import { bindAdminShellEvents } from './events.js';
import { switchAdminView } from './users.js';

document.addEventListener('DOMContentLoaded', async () => {
    bindAdminShellEvents();

    const isAuthenticated = await checkAuth();
    if (!isAuthenticated) return;

    await renderPage();
    switchAdminView('overview');
});
