"""Agent 报告与对话路由。"""

from __future__ import annotations

import json
import threading
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ..agent import graph
from ..agent.pdf import markdown_to_pdf
from ..database import (
    agent_report_by_id,
    agent_reports_by_user,
    analysis_by_id,
    create_agent_report,
    update_agent_report,
)
from ..dependencies import current_user

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])

REPORT_TYPES = {"daily_brief", "deep_dive", "periodic"}


class ReportRequest(BaseModel):
    analysisId: str = Field(alias="analysis_id")
    reportType: str = Field(default="daily_brief", alias="report_type")
    question: str | None = None
    period: str | None = None  # periodic 报告周期：7 / 14 / 30

    model_config = {"populate_by_name": True}


class ChatRequest(BaseModel):
    analysisId: str = Field(alias="analysis_id")
    question: str

    model_config = {"populate_by_name": True}


@router.post("/report", status_code=202)
def create_report(payload: ReportRequest, user=Depends(current_user)) -> dict:
    if payload.reportType not in REPORT_TYPES:
        raise HTTPException(status_code=422, detail="报告类型不支持")
    row = analysis_by_id(payload.analysisId, user["id"])
    if row is None:
        raise HTTPException(status_code=404, detail="分析任务不存在")
    if row["status"] != "completed":
        raise HTTPException(status_code=409, detail="分析尚未完成，无法生成报告")

    report_id = uuid.uuid4().hex
    create_agent_report(report_id, user["id"], payload.analysisId, payload.reportType, payload.question, payload.period)

    def worker():
        try:
            markdown, trace = graph.generate_report(
                payload.analysisId, user["id"], payload.reportType, payload.question, payload.period,
                on_trace=lambda stage, status, detail: update_agent_report(
                    report_id,
                    trace_json=json.dumps({"stage": stage, "status": status, "detail": detail}, ensure_ascii=False),
                ),
            )
            update_agent_report(report_id, status="done", markdown=markdown, completed_at=_utc_now())
        except Exception as error:
            update_agent_report(
                report_id, status="failed",
                markdown=f"报告生成失败：{error}",
                completed_at=_utc_now(),
            )

    threading.Thread(target=worker, daemon=True).start()
    return {"reportId": report_id, "status": "running"}


@router.get("/report/{report_id}")
def get_report(report_id: str, user=Depends(current_user)) -> dict:
    row = agent_report_by_id(report_id, user["id"])
    if row is None:
        raise HTTPException(status_code=404, detail="报告不存在")
    return {
        "reportId": row["id"],
        "analysisId": row["analysis_id"],
        "reportType": row["report_type"],
        "status": row["status"],
        "question": row["question"],
        "period": row["period"],
        "markdown": row["markdown"],
        "progress": json.loads(row["trace_json"]) if row["trace_json"] else None,
        "createdAt": row["created_at"],
        "completedAt": row["completed_at"],
    }


@router.get("/report/{report_id}/pdf")
def download_report_pdf(report_id: str, user=Depends(current_user)) -> Response:
    row = agent_report_by_id(report_id, user["id"])
    if row is None:
        raise HTTPException(status_code=404, detail="报告不存在")
    if row["status"] != "done" or not row["markdown"]:
        raise HTTPException(status_code=409, detail="报告尚未生成完成")
    try:
        pdf_bytes = markdown_to_pdf(row["markdown"])
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"PDF 生成失败：{error}") from error
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="scenicmind_report_{report_id[:8]}.pdf"'},
    )


@router.get("/reports")
def list_reports(user=Depends(current_user)) -> list[dict]:
    rows = agent_reports_by_user(user["id"])
    return [
        {
            "reportId": row["id"],
            "analysisId": row["analysis_id"],
            "reportType": row["report_type"],
            "status": row["status"],
            "question": row["question"],
            "period": row["period"],
            "createdAt": row["created_at"],
            "completedAt": row["completed_at"],
        }
        for row in rows
    ]


@router.post("/chat")
def agent_chat(payload: ChatRequest, user=Depends(current_user)) -> dict:
    row = analysis_by_id(payload.analysisId, user["id"])
    if row is None:
        raise HTTPException(status_code=404, detail="分析任务不存在")
    try:
        answer = graph.chat_answer(payload.analysisId, user["id"], payload.question)
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Agent 回答失败：{error}") from error
    return {"answer": answer}


def _utc_now() -> str:
    from datetime import UTC, datetime
    return datetime.now(UTC).isoformat()
