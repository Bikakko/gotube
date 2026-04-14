# GoTube Windows 开发环境指南

本文档说明如何在 Windows 系统上设置和运行 GoTube 项目。

---

## 📋 环境要求

- **Python**: 3.13 或更高版本
- **操作系统**: Windows 10/11
- **终端**: PowerShell 或 CMD

---

## 🚀 快速开始

### 1. 安装 Python

从 [Python 官网](https://www.python.org/downloads/) 下载并安装 Python 3.13+。

安装时勾选 **"Add Python to PATH"**。

### 2. 创建虚拟环境

在项目根目录运行：

```powershell
# PowerShell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

```cmd
:: CMD
python -m venv venv
venv\Scripts\activate.bat
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 启动服务

#### 方式一：使用启动脚本（推荐）

```powershell
# PowerShell
.\st.bat

# 或指定命令
.\st.bat stop    # 停止服务
.\st.bat restart # 重启服务
.\st.bat status  # 查看状态
```

#### 方式二：直接启动

```bash
# 激活虚拟环境后
uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. 访问服务

启动成功后，在浏览器访问：

- **主页**: http://localhost:8000
- **下载页**: http://localhost:8000/7777
- **管理页**: http://localhost:8000/7777/admin
- **API 文档**: http://localhost:8000/docs（调试模式开启时）

---

## 📁 项目结构

```
gotube/
├── .env                 # 环境配置文件（已创建）
├── .env.example         # 配置模板
├── requirements.txt     # Python 依赖
├── st.bat               # Windows 启动脚本
├── st.sh                # Linux 启动脚本
├── downloads/           # 下载文件存储目录
├── cookies.txt          # 浏览器 Cookies（可选）
├── gotube.db            # SQLite 数据库（自动创建）
├── server.log           # 运行日志
├── server/              # 后端代码
│   ├── main.py          # 应用入口
│   ├── config.py        # 配置管理
│   ├── db.py            # 数据库模型
│   ├── api.py           # API 路由
│   ├── admin_api.py     # 管理页面 API
│   └── downloader.py    # 下载器
└── www/                 # 前端静态文件
    ├── index.html
    ├── download.html
    └── ...
```

---

## ⚙️ 配置说明

所有配置通过 `.env` 文件管理，修改后需要重启服务。

### 重要配置项

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `GOTUBE_PORT` | 服务端口 | 8000 |
| `GOTUBE_HIDDEN_PATH` | 下载页隐藏路径 | 7777 |
| `GOTUBE_MAX_CONCURRENT` | 最大并发下载数 | 5 |
| `GOTUBE_DOWNLOAD_DIR` | 下载目录 | ./downloads |
| `GOTUBE_COOKIES_FILE` | Cookies 文件路径 | ./cookies.txt |
| `GOTUBE_ADMINS` | 管理员账号（用户名:密码） | admin:changeme |
| `GOTUBE_DEBUG` | 调试模式（1=开启） | 1 |
| `GOTUBE_DB_FILE` | 数据库文件路径 | ./gotube.db |

---

## 🔧 常见问题

### 1. 虚拟环境无法激活

**PowerShell 执行策略错误**：

```powershell
# 以管理员身份运行 PowerShell，然后执行：
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 2. 端口被占用

```powershell
# 查找占用端口的进程
netstat -ano | findstr :8000

# 终止进程（替换 PID 为实际值）
taskkill /F /PID <PID>
```

或直接运行：

```powershell
.\st.bat stop
```

### 3. 权限错误

如果遇到权限错误，请以**管理员身份**运行终端。

### 4. yt-dlp 更新

```bash
pip install --upgrade yt-dlp
```

### 5. Cookies 配置

如需下载 YouTube、B站等平台的会员内容：

1. 使用浏览器插件导出 Cookies（Netscape 格式）
2. 将导出的文件替换项目中的 `cookies.txt`

---

## 🐛 开发调试

### 查看日志

日志文件位于 `server.log`，可以使用以下命令实时查看：

```powershell
# PowerShell
Get-Content server.log -Wait -Tail 50

# 或使用 VS Code 等编辑器直接打开
```

### 代码热重载

使用 `--reload` 参数启动后，修改代码会自动重启服务：

```bash
uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
```

### 使用 IDE 调试

推荐使用 **VS Code** 或 **PyCharm**：

1. 打开项目文件夹
2. 选择 Python 解释器为虚拟环境中的解释
3. 配置调试启动项

---

## 📝 与 Linux 版本的差异

| 功能 | Linux | Windows |
|------|-------|---------|
| 启动脚本 | `st.sh` (Bash) | `st.bat` (Batch) |
| 虚拟环境激活 | `source venv/bin/activate` | `.\venv\Scripts\Activate.ps1` |
| 端口检查命令 | `lsof`/`ss` | `netstat` |
| 进程终止 | `kill` | `taskkill` |
| 路径分隔符 | `/` | `\` (代码中已兼容) |

---

## 📚 相关文档

- [操作说明.md](操作说明.md) - 完整功能说明
- [.env.example](.env.example) - 配置模板

---

*最后更新: 2026-04-14 - Windows 开发环境初始设置*
