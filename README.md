<div align="center">

# 🏭 MOLDWISE · 工业注塑机智能体系统

<h3>让注塑机「会思考」—— AI 驱动的工业注塑机智能诊断与工艺优化平台</h3>

`LangGraph` · `FastAPI` · `Vue 3` · `python-a2a`

</div>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/LangGraph-FF6B35?style=flat-square&logo=langchain&logoColor=white" alt="LangGraph" />
  <img src="https://img.shields.io/badge/Vue_3-4FC08D?style=flat-square&logo=vuedotjs&logoColor=white" alt="Vue 3" />
  <img src="https://img.shields.io/badge/MySQL-4479A1?style=flat-square&logo=mysql&logoColor=white" alt="MySQL" />
  <img src="https://img.shields.io/badge/Redis-DC382D?style=flat-square&logo=redis&logoColor=white" alt="Redis" />
  <img src="https://img.shields.io/badge/Milvus-00A1EA?style=flat-square&logo=milvus&logoColor=white" alt="Milvus" />
  <img src="https://img.shields.io/badge/pnpm-4A4A55?style=flat-square&logo=pnpm&logoColor=white" alt="pnpm" />
</p>

<p align="center">
  <img src="https://img.shields.io/github/stars/Scott1314866/Industrial-Multi-Agents?style=flat-square&label=Stars" alt="Stars" />
  <img src="https://img.shields.io/github/forks/Scott1314866/Industrial-Multi-Agents?style=flat-square&label=Forks" alt="Forks" />
  <img src="https://img.shields.io/github/followers/Scott1314866?style=flat-square&label=Followers" alt="Followers" />
</p>

# 🚀 MOLDWISE

**欢迎使用 MOLDWISE！** 🤖 一个面向工业注塑场景的多智能体协作平台，把故障诊断、工艺优化、质量分析与预测性维护收进一个编排图中。

**最后更新：2026 年 8 月** 📅

MOLDWISE 基于 LangGraph 编排多个内部子 Agent，通过 FastAPI 提供 HTTP 与 SSE 接口，前端由 Vue 3 呈现双工作区；内部 Agent 使用进程内 LangGraph 子图协作，A2A 仅用于连接外部 RAG Agent，形成"API 入队 → Worker 执行 → 证据回传"的完整闭环。

## 📑 目录

- [✨ 核心特性](#核心特性)
- [🧱 技术栈](#技术栈)
- [📂 目录结构](#目录结构)
- [🚀 快速启动（PyCharm）](#快速启动pycharm)
- [🔐 开发账号](#开发账号)
- [⚙️ 配置说明](#配置说明)
- [📚 相关文档](#相关文档)
- [🤝 贡献指南](#贡献指南)
- [⚠️ 免责声明](#免责声明)
- [📈 Star History](#star-history)

## ✨ 核心特性

| 特性 | 说明 |
| --- | --- |
| 🧠 **多域编排** | 故障诊断、工艺优化、质量分析、预测性维护，由 `InjectionMoldingOrchestratorGraph` 统一调度 |
| ⚡ **双执行模式** | `inline` 进程内直跑；`redis` 模式 API 入队、Worker 消费 Redis Streams |
| 🔌 **可插拔 RAG** | `RagGateway` seam 隔离，开发用 Fake Adapter，生产经 python-a2a 连外部 RAG |
| 🛡️ **安全门控** | 无证据或门控失败即 fail-closed，不输出具体参数 |
| 🧾 **可审计** | 每次调用按 `thread_id` 隔离 checkpoint、按 `run_id` 关联事件与审计 |

## 🧱 技术栈

| 层 | 技术 |
| --- | --- |
| 🖥️ 后端 | Python 3.12 · FastAPI · LangGraph |
| 🎨 前端 | Vue 3 · Vite · pnpm |
| 🗄️ 存储 | MySQL · Redis · Milvus |
| 🤝 协作 | python-a2a（外部 RAG Agent） |

## 📂 目录结构

```text
Industrial-Multi-Agents
├── backend/src/industrial_agents   # 后端五层：domain / application / infrastructure / web / runtime
├── frontend/                       # Vue 3 前端
├── contracts/                      # RAG A2A 契约
├── docs/                           # 架构与开发手册
├── deploy/                         # Dockerfile 与 nginx
├── scripts/                        # 故障语料导入、建库脚本
├── .env                            # 本机 MySQL / Redis / Milvus 参数（Git 忽略）
└── environment.yml                 # conda 环境定义（ima-agent）
```

## 🚀 快速启动（PyCharm）

> 💡 本机 MySQL、Redis、Milvus 参数已保存在项目根目录 `.env`。PyCharm 直接复用现有 Conda 环境 `ima-agent`，**无需执行 `conda activate`**。

### 1️⃣ 打开项目并配置解释器

1. `File → Open` 打开 `D:\WorkSpace\Industrial-Multi-Agents`。
2. `File → Settings → Project → Python Interpreter → Add Interpreter → Add Local Interpreter → Conda Environment → Existing`，解释器路径填：

   ```text
   D:\Anaconda_envs\envs\ima-agent\python.exe
   ```

3. 在 PyCharm Terminal 验证：

   ```powershell
   python -c "import sys, industrial_agents; print(sys.executable); print(industrial_agents.__file__)"
   ```

   ✅ 应显示 `ima-agent` 解释器与 `backend\src` 路径。

### 2️⃣ 创建 API 启动配置

`Run → Edit Configurations → + → Python`：

| 项 | 值 |
| --- | --- |
| Name | `MOLDWISE API` |
| Run | `Module name` |
| Module name | `industrial_agents.api` |
| Python interpreter | `ima-agent` |
| Working directory | `D:\WorkSpace\Industrial-Multi-Agents` |
| 环境变量 | `PYTHONNOUSERSITE=1` |

🚀 启动后可见 `Uvicorn running on http://127.0.0.1:8080`，文档在 `http://127.0.0.1:8080/docs`。

### 3️⃣ 创建 Worker 启动配置

同上新增 `MOLDWISE Worker`，仅将 Module name 改为 `industrial_agents.worker`，环境变量同样加 `PYTHONNOUSERSITE=1`。

> ⚠️ Redis 执行模式下 **API 与 Worker 必须同时启动**，否则任务会一直排队。

### 4️⃣ 启动 Vue 前端

PyCharm Terminal 中运行：

```powershell
cd D:\WorkSpace\Industrial-Multi-Agents\frontend
corepack pnpm dev
```

打开 `http://localhost:5173`。也可新增 npm Run Configuration：Name `MOLDWISE Frontend`，package.json 指向 `frontend\package.json`，Command `run`、Scripts `dev`、Package manager `pnpm`。

### 5️⃣ 一键启动三个服务

`Run → Edit Configurations → + → Compound`，命名 `MOLDWISE Full Stack`，加入 `MOLDWISE API`、`MOLDWISE Worker`、`MOLDWISE Frontend`，点 Run 即可同时启动。

### 6️⃣ 启动顺序与检查

建议顺序：API → Worker → Frontend。

| 服务 | 地址 |
| --- | --- |
| 🌐 前端 | http://localhost:5173 |
| 📖 Swagger | http://127.0.0.1:8080/docs |
| ❤️ 健康检查 | http://127.0.0.1:8080/healthz |
| ✅ 就绪检查 | http://127.0.0.1:8080/readyz |

> 📌 三个 Run Configuration 的工作目录必须保持为 `D:\WorkSpace\Industrial-Multi-Agents`，否则读不到根目录 `.env`。

## 🔐 开发账号

| 角色 | 账号 | 密码 |
| --- | --- | --- |
| 🧑‍🔧 工程师 | `engineer@moldwise.local` | `Engineer123!` |
| 🤝 客户 | `customer@moldwise.local` | `Customer123!` |
| 🛡️ 管理员 | `admin@moldwise.local` | `Admin123!` |

## ⚙️ 配置说明

- 🧪 环境由 `environment.yml` 定义（`conda env create -f environment.yml`），新机器上可据此重建 `ima-agent`。
- 🏗️ 开发默认使用 SQLite、内存事件总线和 Fake RAG，适合离线开发；`IMA_RAG_MODE=a2a` 切换外部 RAG。
- 🔒 生产环境严禁使用示例 JWT secret、默认账号或 Compose 数据库口令。

## 📚 相关文档

- [🏗️ 当前架构](docs/architecture.md)
- [🛠️ 开发与运行手册](docs/development.md)
- [🤝 RAG A2A 契约](contracts/rag-a2a.md)

## 🤝 贡献指南

1. 🍴 Fork 本仓库并创建功能分支。
2. 💻 本地按「快速启动」搭好 `ima-agent` 环境。
3. 🧪 提交前运行后端与前端测试，确保通过。
4. 📝 用清晰的提交信息描述改动。
5. 🔁 发起 Pull Request，等待 review 合并。

## ⚠️ 免责声明

MOLDWISE 用于辅助工业注塑机的智能诊断与工艺优化，**不替代专业工程师的最终判断**。系统仅读取模拟/外部遥测数据，不提供 PLC 写接口；涉及真实产线的决策请务必由持证工程师复核。本项目面向研究、教学与演示场景，使用者需自行评估部署环境的安全合规风险。

---

**为工业注塑行业的智能升级而构建。** 👨‍💻 让每一条产线更加智慧。🌍

## 📈 Star History

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=Scott1314866/Industrial-Multi-Agents&type=Date&theme=dark" />
  <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=Scott1314866/Industrial-Multi-Agents&type=Date" />
  <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=Scott1314866/Industrial-Multi-Agents&type=Date" />
</picture>
