/**
 * GoTube Admin - ES Module 入口
 *
 * 按原 admin/index.html 的 <script> 顺序加载各业务模块。
 * 各文件已改为规范的 import/export，共享工具直接从 common.module.js 引入。
 */
import './theme.js';
import './state.js';
import './toast.js';
import './render.js';
import './auth.js';
import './data.js';
import './export.js';
import './events.js';
import './users.js';
import './invites.js';
import './cookies.js';
import './system.js';
import './modals.js';
import './admin.js';
