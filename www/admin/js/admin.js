/**
 * GoTube Admin - 主入口文件
 * 初始化 + 模块编排
 * 
 * 依赖加载顺序:
 * 1. common.js (基础工具函数)
 * 2. state.js (全局状态)
 * 3. toast.js (Toast 提示)
 * 4. auth.js (认证模块)
 * 5. render.js (页面渲染)
 * 6. data.js (数据操作)
 * 7. export.js (导出功能)
 * 8. events.js (事件处理)
 * 9. modals.js (模态框)
 * 10. admin.js (本文件 - 主入口)
 */

// ========== 初始化 ==========
document.addEventListener('DOMContentLoaded', async () => {
    // 注入样式
    injectStyles();

    // 检查关键依赖是否已加载
    const requiredDeps = ['checkAuth', 'renderPage', 'renderNavbar', 'loadVideos', 'loadStats'];
    const missingDeps = requiredDeps.filter(fn => typeof window[fn] !== 'function');

    if (missingDeps.length > 0) {
        console.error('关键依赖未加载:', missingDeps);
        // 延迟重试，给 JS 文件更多加载时间
        await new Promise(resolve => setTimeout(resolve, 100));

        const stillMissing = requiredDeps.filter(fn => typeof window[fn] !== 'function');
        if (stillMissing.length > 0) {
            console.error('依赖加载失败，页面无法渲染:', stillMissing);
            document.body.innerHTML = '<div style="color:red;padding:40px;text-align:center;"><h2>页面加载失败</h2><p>请刷新页面重试</p></div>';
            return;
        }
    }

    // 检查认证状态
    const isAuthenticated = await checkAuth();

    if (isAuthenticated) {
        // 认证成功，渲染页面
        await renderPage();
    }
});

// ========== 全局事件监听 ==========

// 点击页面其他地方关闭下拉菜单
document.addEventListener('click', (e) => {
    if (!e.target.closest('.dropdown')) {
        hideAllDropdowns();
    }
});

// ESC 键关闭模态框
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal.active').forEach(modal => {
            modal.remove();
        });
    }
});
