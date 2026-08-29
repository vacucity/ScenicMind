"""经营分析 Agent 编排层。

把意图路由、工具调度、回答组装串起来。会话记忆为进程内 LRU（MVP），
产品化后替换为持久化存储。
"""

from __future__ import annotations

from collections import OrderedDict

from .agent_contracts import ChatResponse
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


def handle_message(message: str, spot: str, session_id: str | None = None) -> ChatResponse:
    message = message.strip()[: _MAX_MSG_LEN]

    # 会话内省略指代：未指定景点时，回落到会话记忆的景点
    effective_spot = spot
    if session_id and (not spot or spot == "黄果树瀑布"):
        remembered = _recall(session_id)
        if remembered and remembered != "黄果树瀑布":
            effective_spot = remembered

    intent = route(message)
    response = respond(intent, effective_spot, message)

    if session_id:
        _remember(session_id, effective_spot)

    return response
