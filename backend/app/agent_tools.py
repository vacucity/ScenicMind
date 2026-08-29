"""经营分析 Agent 工具层——全部只读，返回结构化数据，不负责表达。

每个工具返回 dict，供 Responder 组装自然语言回答。
"""

from __future__ import annotations

from typing import Any

from .module_one_service import build_forecast
from .module_two_service import build_report, list_spots
from .module_two_contracts import ReportRequest, spot_id_for


def query_forecast(spot: str) -> dict[str, Any]:
    """客流预测数据（复用模块一）。"""
    data = build_forecast(spot_id=spot_id_for(spot), spot_name=spot)
    peak = max(data.forecast, key=lambda item: item.predicted)
    return {
        "spot": spot,
        "today": {
            "date": data.today.date.isoformat(),
            "predicted": data.today.predicted,
            "rangeLow": data.today.range_low,
            "rangeHigh": data.today.range_high,
            "level": data.today.level,
            "entered": data.today.entered,
        },
        "peak": {
            "date": peak.date.isoformat(),
            "value": peak.predicted,
            "level": peak.level,
        },
        "week": [
            {"day": item.day, "value": item.value, "level": item.level}
            for item in data.week
        ],
        "capacity": data.capacity,
    }


def query_report(spot: str) -> dict[str, Any]:
    """经营报告（复用模块二）。"""
    report = build_report(ReportRequest(spot_id=spot_id_for(spot), spot_name=spot))
    return {
        "kpis": {
            "forecastTotal": report.kpis.forecast_total,
            "peakDate": report.kpis.peak_date.isoformat(),
            "peakVisitors": report.kpis.peak_visitors,
            "peakCapacityRate": report.kpis.peak_capacity_rate,
            "riskLevel": report.kpis.risk_level,
            "confidence": report.kpis.confidence,
        },
        "executiveSummary": report.executive_summary,
        "recommendations": [
            {
                "recommendationId": item.recommendation_id,
                "priority": item.priority,
                "category": item.category,
                "title": item.title,
                "action": item.action,
                "rationale": item.rationale,
                "expectedImpact": item.expected_impact,
                "evidenceRefs": item.evidence_refs,
            }
            for item in report.recommendations
        ],
        "guardrails": report.guardrails,
    }


def query_accuracy(spot: str) -> dict[str, Any]:
    """预测准确率复盘（演示口径）。

    当前没有真实「历史预测 vs 实际」回测序列，返回演示口径的准确率字段；
    接入真实预测模型后，此处由回测流水线的 MAPE / 偏差计算替换。
    """
    return {
        "spot": spot,
        "mapeDaily": 0.183,
        "mapeThreshold": 0.25,
        "driftDays": [],
        "modelStatus": "normal",
        "passed": True,
        "demo": True,
    }


def query_attribution(spot: str) -> dict[str, Any]:
    """特征贡献度（SHAP 归因口径）。

    归因不单独上屏，只作为 Agent 回答「为什么波动」的隐性输入：
    返回每条驱动因素的 shap（人数贡献）、pct（对峰值占比）与置信度分级。
    接入真实 SHAP 模块后，shap 数值由 explainer 产出替换（当前由模块二驱动因素换算）。
    """
    report = build_report(ReportRequest(spot_id=spot_id_for(spot), spot_name=spot))
    peak = report.kpis.peak_visitors or 1
    total_abs = sum(abs(d.contribution_visitors) for d in report.drivers) or 1

    global_items: list[dict[str, Any]] = []
    for d in sorted(report.drivers, key=lambda x: -abs(x.contribution_visitors)):
        share = abs(d.contribution_visitors) / peak
        ratio_of_total = abs(d.contribution_visitors) / total_abs
        if ratio_of_total >= 0.25:
            confidence = "high"
        elif ratio_of_total >= 0.1:
            confidence = "medium"
        else:
            confidence = "low"
        global_items.append(
            {
                "feature": d.feature,
                "label": d.label,
                "shap": d.contribution_visitors,
                "pct": round(share, 4),
                "direction": d.direction,
                "confidence": confidence,
                "explanation": d.explanation,
            }
        )
    return {
        "reportConfidence": report.kpis.confidence,
        "global": global_items,
        "demo": True,
    }


def query_evidence(spot: str) -> dict[str, Any]:
    """游客原声（证据编号 + 影响分 + 原文链接）。"""
    report = build_report(ReportRequest(spot_id=spot_id_for(spot), spot_name=spot))
    insight = report.visitor_insight
    return {
        "sampleScope": insight.sample_scope,
        "commentCount": insight.comment_count,
        "confidence": insight.confidence,
        "topTopics": [
            {"label": item.label, "count": item.count, "share": item.share}
            for item in insight.top_topics
        ],
        "evidence": [
            {
                "id": item.evidence_id,
                "category": item.category,
                "sentiment": item.sentiment,
                "impactScore": item.impact_score,
                "quote": item.quote,
                "sourceUrl": item.source_url,
            }
            for item in insight.evidence
        ],
    }


def whatif(spot: str, scenario: str) -> dict[str, Any]:
    """受限场景反事实推理。

    scenario 取值：rain / surge / weekday。基于模块一预测做规则化调整，
    输出调整后的峰值与对比。
    """
    base = build_forecast(spot_id=spot_id_for(spot), spot_name=spot)
    peak = max(base.forecast, key=lambda item: item.predicted)

    factor, label = 1.0, ""
    if scenario == "rain":
        factor, label = 0.85, "降雨概率升高"
    elif scenario == "surge":
        factor, label = 1.3, "突发客流（活动/免票）"
    elif scenario == "weekday":
        factor, label = 0.7, "转为工作日"

    adjusted_peak = round(peak.predicted * factor)
    rate_before = peak.predicted / base.capacity
    rate_after = adjusted_peak / base.capacity

    def risk(rate: float) -> str:
        if rate >= 0.9:
            return "高（建议启动限流预案）"
        if rate >= 0.75:
            return "中（建议前置分流）"
        return "低"

    return {
        "scenario": scenario,
        "scenarioLabel": label,
        "peakDate": peak.date.isoformat(),
        "baseValue": peak.predicted,
        "adjustedValue": adjusted_peak,
        "delta": adjusted_peak - peak.predicted,
        "deltaRate": factor - 1.0,
        "capacity": base.capacity,
        "riskBefore": risk(rate_before),
        "riskAfter": risk(rate_after),
    }


def available_spots() -> list[str]:
    return list_spots()
