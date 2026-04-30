# 2026-05-01 任务 3：下载页错误恢复模型

## 范围

- 任务来源：`4.6.0` 计划任务 3
- 目标页面：`www/download.html`、`www/download.js`
- 目标测试：`tests/test_frontend_session_contract_unittest.py`

## 本轮调整

1. 新增统一错误操作区
   - 在下载页主区域加入 `#actionable-error`
   - 支持错误文案和操作按钮分离展示

2. 新增错误恢复辅助函数
   - `renderActionableErrorActions(...)`
   - `showActionableError(...)`
   - `clearActionableError()`
   - `showLoginError(...)`
   - `clearLoginError()`

3. 接入三条关键失败路径
   - 登录失败：在登录弹窗内给出重试和清空密码动作
   - 下载提交失败：给出重试提交和清空输入动作
   - 视频库加载失败：给出重新加载和刷新页面动作

4. 补契约测试
   - 断言下载页存在统一错误操作区
   - 断言三条关键失败路径都接入可恢复动作

## 验证

- `node --check www/download.js`
- `python -m unittest tests.test_frontend_session_contract_unittest -v`
- `node build.js`

结果：

- 下载页脚本语法通过
- 前端契约测试 `13` 项通过
- `www_dist` 构建成功

## 备注

- 本轮只收计划中定义的三条失败路径，没有扩散到其它 fetch 流程。
- 由于当前下载页历史上存在编码污染，本轮新增的关键中文文案优先使用 Unicode 转义，避免再次被终端或脚本错误重编码。
