# 开发与运行

## 本地 Conda 模式

```powershell
conda env create -f environment.yml
Copy-Item .env.example .env
conda run --no-capture-output -n ima-agent python -m industrial_agents.api
```

`conda run` 不依赖 PowerShell 是否加载 Conda hook。若 `conda activate ima-agent` 后 `python` 仍指向 base 环境，执行 `conda init powershell`，关闭所有 PowerShell 窗口后重新打开。

默认使用 SQLite、内存事件总线和 Fake RAG，适合离线开发。若启用 MySQL/Redis：

```powershell
docker compose up -d mysql redis
$env:IMA_DATABASE_URL="mysql+asyncmy://ima:ima_dev_password@127.0.0.1:3306/industrial_agents"
$env:IMA_EXECUTION_MODE="redis"
conda run -n ima-agent python scripts/bootstrap_database.py
conda run --no-capture-output -n ima-agent python -m industrial_agents.api
```

另开终端执行 `conda run --no-capture-output -n ima-agent python -m industrial_agents.worker`。前端使用 `pnpm dev`。

工作区根目录的 `.env` 已按本机 `127.0.0.1:3307` MySQL、带密码的 `127.0.0.1:6379` Redis 和 `127.0.0.1:19530` Milvus 配置，并被 Git 忽略。Milvus 配置只用于就绪探针与外部 RAG 联调；本项目不绕过 A2A 直接检索 Milvus。

## 生产拓扑

API 只负责校验和入队；Worker 消费 Redis Streams 并运行 LangGraph。MySQL 保存长期业务事实；Redis 保存 checkpoint、队列和 SSE 事件。Redis Stack 优先使用官方 checkpoint adapter，标准 Redis 自动使用键值兼容 adapter。RAG 通过 `IMA_RAG_MODE=a2a` 切换。

严禁在生产环境使用示例 JWT secret、默认账号或 Compose 数据库口令。参考工程中出现过的模型密钥和数据库口令应先吊销。

## 故障语料导入

```powershell
python scripts/import_fault_corpus.py `
  --source "D:\WorkSpace\nlp-injection-molding-fault-diagnosis\data" `
  --output .\runtime\fault-scenarios.json
```

导入器只读取 TSV 文本并输出归一化场景；运行时不依赖该绝对路径。
