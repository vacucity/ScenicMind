"""DeepSeek LLM 客户端（可选接入）。

仅在设置环境变量 ``DEEPSEEK_API_KEY`` 后启用；未配置或调用失败时，
``ask`` 返回 ``None``，上层回退到规则 Agent，保证不接 LLM 也能用。
"""

from __future__ import annotations

import json
import os
import urllib.request

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"
_TIMEOUT_SECONDS = 30


def is_configured() -> bool:
    return bool(os.getenv("DEEPSEEK_API_KEY"))


def ask(system_prompt: str, user_message: str) -> str | None:
    """调用 DeepSeek 生成回答；不可用时返回 None。"""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return None

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.3,
        "stream": False,
    }
    request = urllib.request.Request(
        DEEPSEEK_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            body = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None

    try:
        return body["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError):
        return None