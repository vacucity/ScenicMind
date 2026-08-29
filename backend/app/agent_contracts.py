"""经营分析 Agent 对话契约。"""

from typing import Literal

from pydantic import Field

from .module_two_contracts import CamelModel


class ChatRequest(CamelModel):
    message: str = Field(min_length=1, max_length=500)
    spot: str | None = None
    session_id: str | None = None


class EvidenceRef(CamelModel):
    type: Literal["driver", "voice", "metric", "knowledge"]
    label: str
    value: str
    ref: str


class ChatResponse(CamelModel):
    reply: str
    intent: str
    spot: str
    evidence: list[EvidenceRef] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    trace: dict[str, str | bool] = Field(default_factory=dict)