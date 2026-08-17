# 外部 RAG A2A 契约

本工程中 A2A 的唯一用途是连接外部 RAG。内部领域 Agent 不暴露 A2A Server，也不通过 A2A 互调。

## Agent Card

RAG Agent 应声明 JSON 文本输入输出，支持 `diagnosis`、`process`、`quality`、`maintenance` 四个知识域。首版客户端使用 `python-a2a==0.5.4`。

## 请求 Artifact

请求消息的 `TextContent.text` 是 UTF-8 JSON：

```json
{
  "query": "H-08 报警且油温升高",
  "knowledge_domain": "diagnosis",
  "machine_model": "MOLDWISE MX-320",
  "alarm_codes": ["H-08"],
  "tenant_id": "tenant-moldwise-demo",
  "permission_labels": ["engineer", "industrial_manual"],
  "top_k": 5,
  "request_id": "uuid",
  "run_id": "uuid"
}
```

## 完成响应

完成任务的第一个 artifact 文本必须符合：

```json
{
  "status": "success",
  "confidence": 0.91,
  "evidence": [{
    "document_id": "manual-hydraulic-08",
    "title": "MX 系列液压系统维护手册",
    "section": "4.2",
    "snippet": "证据摘要",
    "score": 0.94,
    "version": "2026.1",
    "source_url": "rag://manual-hydraulic-08",
    "access_scope": "internal"
  }],
  "missing_fields": [],
  "warnings": []
}
```

`status` 仅允许 `success/no_evidence/input_required/failed`。RAG 必须执行租户与权限过滤；客户端会拒绝不符合结构的响应。

