from __future__ import annotations

import json

from langchain_openai import ChatOpenAI
from pydantic import SecretStr


class OpenAICompatibleComposer:
    def __init__(self, *, api_key: str, base_url: str, model: str) -> None:
        self.model = ChatOpenAI(
            api_key=SecretStr(api_key),
            base_url=base_url,
            model=model,
            temperature=0.1,
            timeout=20,
            max_retries=1,
        )

    async def compose(self, payload: dict[str, object]) -> str:
        system = (
            "你是工业注塑机诊断汇总模块。只能依据输入 findings 与 evidence，总结为简洁中文。"
            "不得编造型号、数值、引用或维护结论；不得给出可直接写入 PLC 的参数。"
            "高风险时先给停机/隔离提示，再给人工检查步骤。客户角色不得看到内部敏感字段。"
        )
        message = await self.model.ainvoke([("system", system), ("human", json.dumps(payload, ensure_ascii=False))])
        return str(message.content).strip()
