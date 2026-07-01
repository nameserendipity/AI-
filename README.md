# AI 量化交易

基于 ValueCell 的本地化 AI 量化交易与金融多智能体项目，支持通过 Web UI 配置模型、行情数据和交易所连接，用于策略研究、自动交易实验、新闻/研报分析和本地化金融 Agent 工作流。

> ⚠️ 风险提示：本项目仅用于技术研究和量化交易实验，不构成任何投资建议。真实交易可能导致本金损失。请先使用模拟盘、小资金和严格风控验证策略，不要泄露 API Key，不要授予不必要的提现权限。

## 功能亮点

- **多智能体金融分析**：支持研究、新闻检索、策略分析、交易执行等 Agent 工作流。
- **Web 可视化界面**：前端默认运行在 `http://localhost:1420`，便于配置和监控。
- **本地优先**：数据库、向量库、知识库和密钥配置默认保存在本机。
- **多模型接入**：支持 OpenAI、OpenRouter、DeepSeek / SiliconFlow、Google、Azure OpenAI 以及 OpenAI-compatible 服务。
- **交易所连接**：项目代码包含 Binance、OKX、Hyperliquid 等交易所适配能力，实盘前必须自行验证。
- **跨平台启动脚本**：Windows 使用 PowerShell，macOS / Linux 使用 Bash。

## 技术栈

| 模块 | 技术 |
| --- | --- |
| 后端 | Python 3.12+, FastAPI, Uvicorn, SQLAlchemy, Agno, ccxt |
| 前端 | React, React Router, Vite, Tauri, Tailwind CSS |
| 包管理 | uv, bun |
| 数据 | SQLite, LanceDB, 本地知识库目录 |

## 目录结构

```text
.
├── assets/                 # 项目图片和产品截图
├── docs/                   # 配置、架构和发布文档
├── frontend/               # React / Tauri 前端
├── python/                 # Python 后端和 Agent 代码
├── start.ps1               # Windows 一键启动脚本
├── start.sh                # macOS / Linux 一键启动脚本
├── .env.example            # 环境变量示例，不要填写真实密钥后提交
└── README.md               # 当前说明文档
```

## 环境要求

请先安装：

- Python `>= 3.12`
- [uv](https://docs.astral.sh/uv/)
- [bun](https://bun.sh/)
- Windows 用户建议使用 PowerShell 7 或系统 PowerShell

启动脚本会尝试自动检查并安装 `uv` / `bun`，但公开部署或服务器环境建议提前手动安装。

## 快速启动

### 1. 克隆项目

```bash
git clone <你的 GitHub 仓库地址>
cd Ai量化交易
```

### 2. 准备环境变量

复制环境变量模板：

```bash
cp .env.example .env
```

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

然后编辑 `.env`，至少配置你要使用的模型 API Key。交易功能需要额外配置交易所 API Key。

> 不要把 `.env`、交易所密钥、模型密钥提交到 GitHub。

### 3. 启动完整应用

Windows：

```powershell
.\start.ps1
```

macOS / Linux：

```bash
bash start.sh
```

启动后访问：

- Web UI: <http://localhost:1420>
- Backend API: <http://localhost:8000>

## 常用启动命令

### Windows PowerShell

```powershell
# 启动前端 + 后端
.\start.ps1

# 只启动后端
.\start.ps1 -NoFrontend

# 只启动前端
.\start.ps1 -NoBackend

# 查看帮助
.\start.ps1 -Help
```

### macOS / Linux

```bash
# 启动前端 + 后端
bash start.sh

# 只启动后端
bash start.sh --no-frontend

# 只启动前端
bash start.sh --no-backend

# 查看帮助
bash start.sh --help
```

## 手动开发命令

如果不使用一键脚本，也可以分别启动前后端。

后端：

```bash
cd python
uv sync
uv run python -m valuecell.server.main
```

前端：

```bash
cd frontend
bun install
bun run dev
```

代码检查：

```bash
# 后端 lint
make lint

# 后端测试
make test

# 前端检查
cd frontend
bun run typecheck
bun run lint
```

## 配置说明

主要配置文件：

- `.env.example`：环境变量模板
- `docs/CONFIGURATION_GUIDE.md`：详细配置说明
- `python/configs/`：模型、Provider、Agent 等配置文件

常见关键配置：

| 变量 | 说明 |
| --- | --- |
| `VALUECELL_HOME` | 本地数据目录，保存 `.env`、SQLite、LanceDB 和知识库 |
| `API_HOST` / `API_PORT` | 后端监听地址和端口，默认 `localhost:8000` |
| `OPENAI_API_KEY` | OpenAI API Key |
| `OPENROUTER_API_KEY` | OpenRouter API Key |
| `SILICONFLOW_API_KEY` | SiliconFlow / DeepSeek 相关模型 Key |
| `TAVILY_API_KEY` | Web 搜索能力 Key |
| `SEC_EMAIL` | SEC/EDGAR 数据访问身份邮箱 |

## GitHub 提交前检查

提交前建议执行：

```bash
git status --short
```

确保以下内容没有被提交：

- `.env`
- `*.key`
- `frontend/node_modules/`
- `python/.venv/`
- `.venv/`
- `logs/`
- 本地数据库、向量库、知识库
- 任何真实交易所 API Key 或模型 API Key

更多检查项见：`docs/GITHUB_RELEASE_CHECKLIST.md`。

## GitHub 初始化示例

当前目录如果还不是 git 仓库，可以按下面流程初始化：

```bash
git init
git add .
git commit -m "Initial open-source release"
git branch -M main
git remote add origin https://github.com/<你的用户名>/<你的仓库名>.git
git push -u origin main
```

如果 GitHub 仓库已经存在，请把 `origin` 地址替换为你的实际仓库地址。

## 安全建议

- 交易所 API Key 建议只开启必要权限，不开启提现权限。
- 使用 IP 白名单限制 API Key 调用来源。
- 实盘前先跑模拟盘或小资金。
- 定期轮换密钥。
- 不要在 Issue、截图、日志或提交记录中暴露密钥。

## License

本项目基于 Apache-2.0 License。详见 `LICENSE`。

## 致谢

本项目基于 ValueCell 生态和相关开源组件进行本地化整理与二次开发。
