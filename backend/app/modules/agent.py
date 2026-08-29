"""经营分析 Agent 对话 API。"""

from typing import Annotated

from fastapi import APIRouter, Query

from .. import agent_tools as tools
from ..agent_contracts import ChatRequest, ChatResponse
from ..agent_orchestrator import handle_message

router = APIRouter(prefix="/api/v1/agent", tags=["经营分析 Agent"])


@router.post("/chat", response_model=ChatResponse, response_model_by_alias=True)
def chat(request: ChatRequest) -> ChatResponse:
    return handle_message(request.message, request.spot, request.session_id)


@router.get("/report")
def agent_report(
    spot: Annotated[str, Query(min_length=1, max_length=80)] = "九寨沟",
) -> dict:
    """返回四段式经营报告的结构化数据，供前端「Agent 报告」页直接渲染。"""
    accuracy = tools.query_accuracy(spot)
    attribution = tools.query_attribution(spot)
    report = tools.query_report(spot)
    kpis = report["kpis"]

    return {
        "spot": spot,
        "title": f"{spot}经营决策周报",
        "accuracy": {
            "mapeDaily": accuracy["mapeDaily"],
            "mapeThreshold": accuracy["mapeThreshold"],
            "passed": accuracy["passed"],
            "modelStatus": accuracy["modelStatus"],
            "driftDays": accuracy["driftDays"],
        },
        "attribution": attribution["global"],
        "reportConfidence": attribution["reportConfidence"],
        "recommendations": report["recommendations"],
        "risk": {
            "peakDate": kpis["peakDate"],
            "peakCapacityRate": kpis["peakCapacityRate"],
            "peakVisitors": kpis["peakVisitors"],
            "riskLevel": kpis["riskLevel"],
        },
    }