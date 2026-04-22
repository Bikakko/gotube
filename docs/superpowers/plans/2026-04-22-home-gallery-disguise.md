# 首页伪装相册站实现计划

> **面向 AI 代理的工作说明：** 必须按任务顺序实现，先补测试，再写实现。每个任务完成后做最小验证，再继续下一步。

**目标：** 将根路径改造成公开可浏览的伪装相册首页，同时保持隐藏业务入口不变。

**架构：** 后端提供最小图库只读接口，前端首页动态拉取相册列表与相册详情。图片数据来自仓库根目录 `gallery/` 下的一级子目录。

**技术栈：** FastAPI、原生 HTML/CSS/JS、现有 4.2.0 安全响应头与路由硬化。

---

### 任务 1：图库目录模型与安全工具

**文件：**

- 创建：`server/gallery.py`
- 测试：`tests/test_gallery_unittest.py`

- [ ] **步骤 1：编写失败测试**

覆盖：

- 只识别 `gallery/` 下一级子目录
- 只识别白名单图片扩展
- 非法 `slug` / `name` 被拒绝
- 越界路径被拒绝

- [ ] **步骤 2：运行测试确认失败**

运行：

```bash
python -m unittest tests.test_gallery_unittest
```

- [ ] **步骤 3：实现最小图库扫描与路径解析**

提供能力：

- 列出有效相册
- 列出单相册图片
- 解析安全图片路径

- [ ] **步骤 4：重新运行测试确认通过**

### 任务 2：图库接口接入

**文件：**

- 修改：`server/api.py`
- 修改：`server/main.py`（如需挂载）
- 测试：`tests/test_gallery_api_unittest.py`

- [ ] **步骤 1：编写失败测试**

覆盖：

- `GET /api/gallery/albums`
- `GET /api/gallery/albums/{slug}`
- `GET /api/gallery/image/{slug}/{name}`
- 非法参数和不存在资源返回 `404`

- [ ] **步骤 2：运行测试确认失败**

- [ ] **步骤 3：实现接口**

要求：

- 不暴露真实路径
- 图片走受控端点
- 响应字段固定

- [ ] **步骤 4：重新运行测试确认通过**

### 任务 3：首页伪装相册 UI

**文件：**

- 修改：`www/index.html`
- 创建或修改：`www/index.js`
- 可选创建：`www/index.css`
- 测试：`tests/test_home_gallery_frontend_unittest.py`

- [ ] **步骤 1：编写失败测试**

覆盖：

- 首页存在相册卡片容器
- 首页存在模态结构或挂点
- 首页不出现下载业务文案
- 首页存在隐蔽入口挂点

- [ ] **步骤 2：运行测试确认失败**

- [ ] **步骤 3：实现首页结构**

要求：

- 相册卡片网格
- 米哈游风格的轻动效
- 相册文案语义
- 不暴露业务信息

- [ ] **步骤 4：重新运行测试确认通过**

### 任务 4：首页数据与模态交互

**文件：**

- 修改：`www/index.js`
- 测试：`tests/test_home_gallery_frontend_unittest.py`

- [ ] **步骤 1：补失败测试**

覆盖：

- 拉取相册列表
- 点击卡片打开模态
- 左右翻页按钮存在
- 键盘左右键与 Esc 行为入口存在

- [ ] **步骤 2：运行测试确认失败**

- [ ] **步骤 3：实现最小交互**

要求：

- 首页加载相册列表
- 点击卡片后拉取相册详情
- 模态中左右翻页
- 关闭行为完整

- [ ] **步骤 4：重新运行测试确认通过**

### 任务 5：隐蔽入口与占位资源

**文件：**

- 修改：`www/index.html`
- 可选创建：`www/static` 或直接复用现有资源
- 测试：`tests/test_home_gallery_frontend_unittest.py`

- [ ] **步骤 1：补失败测试**

覆盖：

- 隐蔽入口跳转到 `/{hidden_path}`
- 不出现明显业务 CTA 文案

- [ ] **步骤 2：运行测试确认失败**

- [ ] **步骤 3：实现入口挂点**

要求：

- 使用占位图片或占位容器
- 后续可直接替换为管理员上传的动态图片

- [ ] **步骤 4：重新运行测试确认通过**

### 任务 6：文档与回归

**文件：**

- 修改：`操作说明.md`
- 可选新增：`docs/ops/gallery-home.md`
- 测试：相关 unittest + `node --check`

- [ ] **步骤 1：补充运维说明**

说明：

- `gallery/` 目录结构
- 支持图片格式
- 如何手工上传目录和图片

- [ ] **步骤 2：跑总验证**

运行：

```bash
python -m unittest tests.test_gallery_unittest tests.test_gallery_api_unittest tests.test_home_gallery_frontend_unittest
node --check www/index.js
python -m py_compile server/gallery.py server/api.py server/main.py
git diff --check
```

- [ ] **步骤 3：提交变更**

提交信息建议：

```bash
git commit -m "feat(home): 新增伪装相册首页"
```
