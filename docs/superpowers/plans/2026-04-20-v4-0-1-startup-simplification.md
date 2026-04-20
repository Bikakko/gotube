# GoTube V4.0.1 启动与配置收敛实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。
**目标：** 让 GoTube 的开发/生产启动流程尽量收敛为少量固定命令，并把运行参数尽量收敛到 `.env` 中管理。

**架构：** 引入共享 shell 启动库，统一 `st.sh` / `wk.sh` 的配置读取、虚拟环境初始化、依赖安装和环境诊断逻辑；脚本本身只保留模式差异和最终启动命令。

**技术栈：** Bash、Python venv、pip、gunicorn、uvicorn、unittest。

---

## 文件结构

| 文件 | 操作 | 职责 |
| --- | --- | --- |
| `scripts/gotube_runtime.sh` | 创建 | 启动配置读取、路径解析、初始化、doctor、自检、公用命令 |
| `wk.sh` | 修改 | 生产启动壳层，支持 init/doctor/start/restart/status/update |
| `st.sh` | 修改 | 开发启动壳层，支持 init/doctor/start/restart/status |
| `.env.example` | 修改 | 收敛启动相关配置项 |
| `tests/test_start_script_unittest.py` | 修改 | 覆盖启动命令和 `.env` 约定 |
| `操作说明.md` | 修改 | 记录新的最小启动流程 |

---
