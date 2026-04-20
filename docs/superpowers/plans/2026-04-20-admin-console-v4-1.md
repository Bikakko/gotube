# GoTube V4.1 管理后台重构实施计划

## 目标

将当前后台收口为顶部导航驱动的单页管理台，明确区分：

- 概览
- 全局媒体
- 用户
- 邀请码
- 系统

重点解决两类问题：

1. 语义混乱：全局媒体与用户视频库混在一起。
2. 规模增长：用户数量、媒体数量增长后，筛选和详情区域会明显变差。

## 当前实施顺序

1. 已完成：任务 16.1 顶部导航和后台骨架
2. 已完成：任务 16.2 全局媒体资产视图
3. 进行中：任务 16.3 用户页重做与规模适配
4. 待完成：任务 16.4 邀请码页接入新骨架
5. 待完成：任务 16.5 系统页整合 Cookie 与健康检查
6. 待完成：任务 16.6 收口旧逻辑并做总回归

## 任务 16.3：用户页重做与规模适配

### 目标

- 用户页只负责用户管理，不再承担全局媒体视图语义。
- 管理员可以从用户页直接查看指定用户的视频库。
- 当用户数量增长时，归属筛选不再依赖长下拉滚动。
- 当某条媒体的拥有者或来源很多时，详情弹窗仍然可用。
- 当媒体总量增长时，管理员不必只能用滚轮慢慢翻页。

### 涉及文件

- `server/admin_api.py`
- `tests/test_admin_management_unittest.py`
- `www/admin/js/state.js`
- `www/admin/js/data.js`
- `www/admin/js/events.js`
- `www/admin/js/render.js`
- `www/admin/js/users.js`
- `www/admin/js/modals.js`
- `www/admin/css/admin.css`

### 具体要求

#### A. 用户页

- 用户列表中增加“视频库”入口。
- 用户列表支持本地搜索，至少覆盖用户名、ID、角色、状态。
- 点击后打开该用户的视频库弹窗。
- 弹窗只展示该用户拥有的逻辑条目，不混入全局媒体卡片语义。

#### B. 归属筛选

- 归属筛选改为可搜索下拉。
- 默认仍保留：
  - 全部
  - 未归属
  - 指定用户
- 用户候选渲染数量需要限制，避免一次性渲染超长列表。

#### C. 媒体详情

- “拥有者”列表默认仅展示前 10 条。
- “来源链接”列表默认仅展示前 10 条。
- 超出部分通过“展开全部 / 收起”切换。
- 列表区域自身滚动，不让整个弹窗无限拉长。

#### D. 媒体翻页

- 每页数量支持：
  - 20
  - 50
  - 100
- 切换页大小后重置到第一页。

### 验证

至少执行：

```bash
.\venv\Scripts\python.exe -m unittest tests.test_admin_management_unittest
node --check www/admin/js/data.js
node --check www/admin/js/events.js
node --check www/admin/js/render.js
node --check www/admin/js/users.js
node --check www/admin/js/modals.js
git diff --check
```

## 后续任务

### 任务 16.4：邀请码页接入新骨架

- 让邀请码页完全依附顶部导航和新视图状态。
- 清理旧的 `currentView === 'videos'` 一类分支依赖。

### 任务 16.5：系统页整合

- 将 Cookie 管理、诊断、健康检查统一收口到系统页。

### 任务 16.6：总回归

- 清理旧视图遗留逻辑。
- 补后台整体回归测试。
- 做一次前端语法检查和后端接口回归。
