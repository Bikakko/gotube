# GoTube Windows 开发环境指南 (v4.10.0)

本文指南说明如何在 Windows 10/11 环境下部署、运行与调试 GoTube 项目。

---

## 一、 环境要求

- **Python**: 3.13 或更高版本
- **操作系统**: Windows 10 / 11
- **终端**: PowerShell 或 CMD
- **FFmpeg**: 建议配置在系统 PATH 或虚拟环境中

---

## 二、 快速开始

### 1. 创建并激活虚拟环境

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

### 2. 安装依赖

```powershell
pip install -r requirements.txt
```

### 3. 启动本地开发服务

可以使用便捷批处理脚本 `st.bat`：

```powershell
.\st.bat         # 启动开发服务器（前台带热重载）
.\st.bat stop    # 停止服务
.\st.bat restart # 重启服务
.\st.bat status  # 查看状态
```

或使用直接命令行启动：

```powershell
uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 三、 配置说明 (`.env`)

关键配置变量：

| 变量名 | 说明 | 默认值 |
|---|---|---|
| `GOTUBE_PORT` | 服务端口 | `8000` |
| `GOTUBE_HIDDEN_PATH` | 隐藏下载页与后台路径 | `7777` |
| `GOTUBE_MAX_CONCURRENT` | 全局最大并发下载任务数 | `5` |
| `GOTUBE_MAX_DOWNLOADS_PER_USER` | 单用户最大同时下载数（0=不限制） | `1` |
| `GOTUBE_DOWNLOAD_DIR` | 视频存储目录 | `./downloads` |
| `GOTUBE_COOKIES_FILE` | Cookies 凭据路径 | `./data/cookies.txt` |
| `GOTUBE_ADMINS` | 超级管理员（用户名:密码） | `admin:changeme` |
| `GOTUBE_DB_FILE` | SQLite 数据库文件路径 | `./gotube.db` |

---

## 四、 项目核心目录结构

```text
gotube/
├── .env                 # 环境配置文件
├── .env.example         # 配置模板
├── requirements.txt     # Python 依赖
├── st.bat               # Windows 启动脚本
├── downloads/           # 下载视频存储目录
├── data/
│   └── cookies.txt      # 浏览器 Cookies 文件
├── gotube.db            # SQLite 数据库
├── server/              # 后端 Python 代码 (FastAPI)
├── www/                 # 前端源码 (ES Module 架构)
└── docs/
    └── manuals/         # 使用与运维文档
```
