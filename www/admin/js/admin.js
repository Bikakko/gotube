/**
 * GoTube Admin - application bootstrap
 */

document.addEventListener('DOMContentLoaded', async () => {
    const requiredDeps = ['checkAuth', 'renderPage', 'renderNavbar', 'bindAdminShellEvents', 'switchAdminView'];
    const missingDeps = requiredDeps.filter(fn => typeof window[fn] !== 'function');

    if (missingDeps.length > 0) {
        console.error('关键依赖未加载:', missingDeps);
        await new Promise(resolve => setTimeout(resolve, 100));

        const stillMissing = requiredDeps.filter(fn => typeof window[fn] !== 'function');
        if (stillMissing.length > 0) {
            console.error('依赖加载失败，页面无法渲染:', stillMissing);
            document.body.innerHTML = '<div style="color:red;padding:40px;text-align:center;"><h2>页面加载失败</h2><p>请刷新页面重试</p></div>';
            return;
        }
    }

    bindAdminShellEvents();

    const isAuthenticated = await checkAuth();
    if (!isAuthenticated) return;

    await renderPage();
    switchAdminView('overview');
});
