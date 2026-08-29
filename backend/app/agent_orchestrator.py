"""经营分析 Agent 编排层。

把意图路由、工具调度、回答组装串起来。会话记忆为进程内 LRU（MVP），
产品化后替换为持久化存储。
"""

from __future__ import annotations

from collections import OrderedDict

from . import agent_llm as llm
from .agent_contracts import ChatResponse
from .agent_knowledge import build_context
from .agent_responder import respond
from .agent_router import route

_SESSIONS: OrderedDict[str, str] = OrderedDict()
_MAX_SESSIONS = 256
_MAX_MSG_LEN = 500


def _remember(session_id: str, spot: str) -> None:
    if not session_id:
        return
    _SESSIONS[session_id] = spot
    _SESSIONS.move_to_end(session_id)
    while len(_SESSIONS) > _MAX_SESSIONS:
        _SESSIONS.popitem(last=False)


def _recall(session_id: str) -> str | None:
    return _SESSIONS.get(session_id)


def handle_message(message: str, spot: str | None = None, session_id: str | None = None) -> ChatResponse:
    message = message.strip()[: _MAX_MSG_LEN]

    # 会话内省略指代：未指定景点时，回落到会话记忆的景点；仍无则用默认景点。
    effective_spot = spot
    if session_id and not spot:
        remembered = _recall(session_id)
        if remembered:
            effective_spot = remembered
    if not effective_spot:
        effective_spot = "九寨沟"

    if session_id:
        _remember(session_id, effective_spot)

    # 接入 LLM 时，走「有问必答 + 内置知识库」；未配置或调用失败则回退规则 Agent。
    if llm.is_configured():
        reply = llm.ask(build_context(effective_spot), message)
        if reply:
            return ChatResponse(
                reply=reply,
                intent="llm",
                spot=effective_spot,
                evidence=[],
                suggestions=["给我一份周报", "这几天人为什么变多？", "如果下周下雨呢？"],
                trace={
                    "agentVersion": "scenicmind-agent-v2",
                    "intentSource": "llm-deepseek",
                    "generationMode": "llm",
                    "evidenceBound": True,
                },
            )

    intent = route(message)
    return respond(intent, effective_spot, message)
