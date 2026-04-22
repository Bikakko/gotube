# GoTube V4.3.0 管理后台体验重做实施计划

## 目标

在不推翻现有后台信息架构和核心接口的前提下，完成一次后台体验重做。重点提升：

- 视觉统一性
- 卡片与工具栏的可读性
- 操作主次
- 正式提示文案
- 手机端可用性

## 任务拆分

### 任务 1：建立后台新版视觉 token

涉及文件：

- `www/admin/css/admin.css`

实施内容：

- 重写颜色变量，退掉旧红黑主色体系
- 建立月夜工作台风格的背景、面板、描边、高光、危险色
- 统一圆角、阴影、边框和层级变量

验证：

- `git diff --check`

### 任务 2：公共组件与头部样式重做

涉及文件：

- `www/admin/admin.html`
- `www/admin/css/admin.css`

实施内容：

- 重做顶部导航头部
- 统一按钮、输入框、下拉、标签、弹窗壳层
- 统一工具栏、面板和空状态基础样式
- 确保手机端导航和公共控件可用

验证：

- `git diff --check`

### 任务 3：全局媒体页体验重做

涉及文件：

- `www/admin/js/render.js`
- `www/admin/js/events.js`
- `www/admin/js/modals.js`
- `www/admin/css/admin.css`

实施内容：

- 将媒体卡片重构为信息卡
- 收口主操作数量
- 重做筛选工具栏样式和布局
- 重做媒体详情弹窗的层次、分组和状态表达
- 保证缩略图、时长、状态信息更容易扫读

验证：

- `node --check www/admin/js/render.js`
- `node --check www/admin/js/events.js`
- `node --check www/admin/js/modals.js`
- `git diff --check`

### 任务 4：用户页体验重做

涉及文件：

- `www/admin/js/users.js`
- `www/admin/js/render.js`
- `www/admin/css/admin.css`

实施内容：

- 强化用户搜索区
- 统一状态、角色、容量的视觉标签
- 收口行内操作
- 统一用户视频库弹窗样式
- 保证手机端用户列表可读

验证：

- `node --check www/admin/js/users.js`
- `node --check www/admin/js/render.js`
- `git diff --check`

### 任务 5：系统页与邀请码页视觉接入

涉及文件：

- `www/admin/js/system.js`
- `www/admin/js/invites.js`
- `www/admin/css/admin.css`

实施内容：

- 将系统页整理为状态面板
- 统一 Cookie、健康检查、诊断的状态表达
- 邀请码页接入新版工具栏和列表风格

验证：

- `node --check www/admin/js/system.js`
- `node --check www/admin/js/invites.js`
- `git diff --check`

### 任务 6：文案收口与移动端回归

涉及文件：

- `www/admin/js/render.js`
- `www/admin/js/users.js`
- `www/admin/js/modals.js`
- `www/admin/js/system.js`
- `www/admin/js/invites.js`
- `www/admin/js/toast.js`
- `www/admin/css/admin.css`

实施内容：

- 清理临时性提示文案
- 统一成功/失败/空状态/确认提示
- 检查手机端下导航、卡片、工具栏、弹窗布局
- 修正窄屏下的按钮密度和换行问题

验证：

- `node --check www/admin/js/render.js`
- `node --check www/admin/js/users.js`
- `node --check www/admin/js/modals.js`
- `node --check www/admin/js/system.js`
- `node --check www/admin/js/invites.js`
- `node --check www/admin/js/toast.js`
- `git diff --check`

## 建议实施顺序

1. 任务 1
2. 任务 2
3. 任务 3
4. 任务 4
5. 任务 5
6. 任务 6

## 总体验证

建议在任务完成后至少执行：

```bash
node --check www/admin/js/render.js
node --check www/admin/js/users.js
node --check www/admin/js/modals.js
node --check www/admin/js/system.js
node --check www/admin/js/invites.js
node --check www/admin/js/toast.js
git diff --check
```

如果环境允许，再补一轮后台人工验收，重点覆盖：

- 顶部导航切换
- 全局媒体卡片阅读与操作
- 用户搜索和视频库入口
- 系统页状态查看
- 邀请码页创建与查看
- 手机端布局
