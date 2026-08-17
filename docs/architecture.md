# MOLDWISE 当前架构

本文档描述当前代码，而 `injection-molding-a2a-system-design.md` 保留为早期 A2A 全互联方案的参考资料。

```mermaid
flowchart LR
  UI[Vue 双工作区] --> API[FastAPI HTTP Adapter]
  API --> DB[(MySQL)]
  API --> Q[Redis Streams]
  Q --> W[Graph Worker]
  W --> G[InjectionMoldingOrchestratorGraph]
  G --> D[故障诊断]
  G --> P[工艺优化]
  G --> QL[质量分析]
  G --> M[预测性维护]
  D & P & QL & M --> RG[RagGateway Seam]
  RG --> FR[Fake Adapter]
  RG --> AR[python-a2a Adapter]
  AR --> RAG[外部 RAG]
  G --> CP[(Redis Checkpoint)]
```

## 模块职责

- `domain` 定义稳定 Interface 和工业类型，不依赖 Web、数据库或 A2A。
- `application` 隐藏 LangGraph 路由、并行分支、证据聚合和安全门控。
- `infrastructure` 提供 MySQL、Redis、模拟遥测、OpenAI 兼容模型和 A2A Adapter。
- `web` 只处理鉴权、DTO、错误映射和 SSE，不包含 Agent 决策。
- `runtime` 组合 Adapter，并在 inline 与 Redis Worker 两种执行模式间切换。

## 关键约束

1. A2A 只允许出现在 `RagGateway` seam。
2. LLM 不接收数据库连接，也不能生成可执行 SQL。
3. 系统只读取模拟/外部遥测，不提供 PLC 写 Interface。
4. 无证据或安全门控失败时采用 fail-closed，不输出具体参数。
5. 每个图调用按 `thread_id` 隔离 checkpoint，并按 `run_id` 关联事件和审计。

