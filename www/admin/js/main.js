/**
 * GoTube Admin - ES Module 入口
 *
 * 先加载全局兼容层（填充 window.$ / el / apiFetch / GoTubeSession 等），
 * 再按原 admin/index.html 的 <script> 顺序加载各业务文件。
 * 业务文件内部仍以 window.xxx 共享函数，故加载顺序必须与原顺序一致。
 */
import '../../shared/globals.js';
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
