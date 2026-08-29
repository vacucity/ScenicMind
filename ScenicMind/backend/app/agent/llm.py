"""轻量 LLM 客户端 —— OpenAI 兼容协议，urllib 直调，零额外依赖。

黑客松原则：不引入 langchain/langgraph 重依赖，工作流用纯 Python 状态机实现。
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any

from .config import AGENT_LLM_BASE_URL, AGENT_LLM_MAX_TOKENS, AGENT_LLM_MODEL, AGENT_LLM_TIMEOUT, llm_headers


class LLMUnavailableError(RuntimeError):
    """所有 provider 均不可用（触发模板化降级）。"""


def chat(messages: list[dict[str, str]], temperature: float = 0.3, json_mode: bool = False) -> str:
    """调用 LLM，返回文本。失败抛 LLMUnavailableError。"""
    payload: dict[str, Any] = {
        "model": AGENT_LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": AGENT_LLM_MAX_TOKENS,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    request = urllib.request.Request(
        f"{AGENT_LLM_BASE_URL.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers=llm_headers(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=AGENT_LLM_TIMEOUT) as response:
            body = json.loads(response.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"]
    except Exception as error:
        raise LLMUnavailableError(f"LLM 调用失败：{error}") from error


def chat_json(messages: list[dict[str, str]], temperature: float = 0.2) -> dict[str, Any]:
    """调用 LLM 并解析 JSON 输出。"""
    text = chat(messages, temperature=temperature, json_mode=True)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 容错：截取首个 { 到末个 } 之间的内容
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise
