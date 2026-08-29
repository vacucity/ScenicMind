"""多 Agent 协作工作流 —— Coordinator → Collector → Analyst → Writer → Reviewer。

纯 Python 状态机（不依赖 langgraph），每阶段轨迹写入 trace 供前端展示。
LLM 不可用时自动降级为模板化报告（保证 demo 永不白屏）。
"""

from __future__ import annotations

import json
import traceback
from datetime import datetime, UTC
from typing import Any

from . import prompts
from .llm import LLMUnavailableError, chat, chat_json
from .tools import collect_all


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _compact_data(data: dict[str, Any]) -> str:
    """压缩数据包给 LLM（控制 token）。"""
    forecast = data.get("forecast") or {}
    indicators = data.get("indicators") or {}
    importance = data.get("importance") or {}
    compact = {
        "forecast": {
            "latestActual": forecast.get("latestActual"),
            "nextForecast": forecast.get("nextForecast"),
            "horizons": forecast.get("horizons"),
            "metrics": forecast.get("metrics"),
        },
        "indicators": {
            k: {kk: vv for kk, vv in v.items() if kk != "recent30" and not isinstance(vv, (list, dict))}
            for k, v in indicators.items() if isinstance(v, dict)
        },
        "importance": {"semantic_groups": importance.get("semantic_groups", [])},
        "gaps": data.get("gaps", []),
    }
    return json.dumps(compact, ensure_ascii=False)


def run_analyst(data: dict[str, Any], question: str | None, report_type: str = "deep_dive", period: str | None = None) -> dict[str, Any]:
    system = prompts.ANALYST_SYSTEMS.get(report_type, prompts.ANALYST_SYSTEM)
    user_prompt = f"数据包：\n{_compact_data(data)}\n\n"
    if report_type == "periodic" and period:
        user_prompt += f"本次周期：{period} 天。请以 {period} 天为统计周期，重点分析未来 {period} 天的客流预测、与该周期对应的趋势规律与阶段性对比。\n"
    if question:
        user_prompt += f"用户重点关注问题：{question}\n请围绕该问题深入分析，其他维度作为辅助证据。\n"
    return chat_json([
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt},
    ])


def run_writer(data: dict[str, Any], analysis: dict[str, Any], report_type: str, question: str | None, period: str | None = None) -> str:
    system = prompts.WRITER_SYSTEMS.get(report_type, prompts.WRITER_SYSTEM)
    type_label = {"daily_brief": "每日简报", "deep_dive": "深度分析", "periodic": "周期报告"}.get(report_type, "经营分析")
    period_label = f"（{period} 天周期）" if report_type == "periodic" and period else ""
    user_prompt = (
        f"报告类型：{type_label}{period_label}\n"
        + (f"统计周期：{period} 天\n" if report_type == "periodic" and period else "")
        + (f"报告主标题务必标注周期，如「# 周期经营报告（{period} 天周期）」\n" if report_type == "periodic" and period else "")
        + (f"重点主题：{question}\n" if question else "")
        + f"分析要点：\n{json.dumps(analysis, ensure_ascii=False)}\n\n"
        + f"数据包摘要：\n{_compact_data(data)}\n\n请撰写报告。"
    )
    return chat([
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt},
    ], temperature=0.4)


def run_reviewer(data: dict[str, Any], markdown: str) -> dict[str, Any]:
    user_prompt = f"数据包：\n{_compact_data(data)}\n\n待审核报告：\n{markdown}\n\n请校验。"
    return chat_json([
        {"role": "system", "content": prompts.REVIEWER_SYSTEM},
        {"role": "user", "content": user_prompt},
    ], temperature=0.1)


def _template_report(data: dict[str, Any], report_type: str, question: str | None, period: str | None = None) -> str:
    """降级模板：LLM 不可用时的确定性数据简报。"""
    forecast = data.get("forecast") or {}
    indicators = data.get("indicators") or {}
    importance = data.get("importance") or {}
    vt = indicators.get("visitorTrend", {})
    cap = indicators.get("capacity", {})
    hol = indicators.get("holidayEffect", {})
    latest = forecast.get("latestActual", {})
    nxt = forecast.get("nextForecast") or {}
    h7 = (forecast.get("horizons") or {}).get("7", {})
    metrics = forecast.get("metrics", {})
    groups = importance.get("semantic_groups", [])
    top_group = groups[0] if groups else {}

    type_title = {"daily_brief": "每日经营简报", "deep_dive": "深度经营分析报告", "periodic": "周期经营报告"}.get(report_type, "景区经营分析报告")
    period_suffix = f"（{period} 天周期）" if report_type == "periodic" and period else ""
    lines = [
        f"# {type_title}{period_suffix}（数据简报）",
        "",
        "> 注：AI 分析服务暂不可用，以下为基于数据的确定性简报。",
        "",
        "## 一、客流预测概要",
        f"- 最新真实客流：**{latest.get('visitors', '—')} 人**（{latest.get('date', '—')}）",
        f"- 下一日预测：**{nxt.get('predictedVisitors', '—')} 人**（{nxt.get('date', '—')}）",
        f"- 未来 7 天日均：**{h7.get('average', '—')} 人**，区间 {h7.get('minimum', '—')}–{h7.get('peak', '—')} 人",
        f"- 模型回测：MAPE {metrics.get('mape', '—')}%，MAE {metrics.get('mae', '—')} 人",
        "",
        "## 二、关键发现",
        f"- 客流同比变化 **{vt.get('yoyChange', '—')}%**，环比 **{vt.get('momChange', '—')}%**",
        f"- 平均载客率 **{cap.get('avgLoadRate', '—')}%**，售罄 {cap.get('soldOutDays', '—')} 天，限流 {cap.get('restrictedDays', '—')} 天",
        f"- 节假日效应提升 **{hol.get('holidayLift', '—')}%**（节假日日均 {hol.get('holidayAvg', '—')} vs 平日 {hol.get('weekdayAvg', '—')}）",
        f"- 客流最主要驱动因素：**{top_group.get('label', '—')}（{top_group.get('importance', '—')}%）**",
    ]
    if question:
        lines.append(f"- 用户关注主题：{question}")
    lines += [
        "",
        "## 三、风险预警",
        f"- 封顶天数 {json.loads(json.dumps(indicators.get('dataQuality', {}))).get('cappedDays', '—')} 天（需求被承载上限截断，实际需求可能更高）",
        "",
        "## 四、行动建议",
        "- 下一日预测接近承载上限时，提前公告预约分流",
        "- 关注 7 日滚动趋势拐点，安排弹性运力",
        "- 节假日前置检查票务额度与限流预案",
    ]
    return "\n".join(lines)


def generate_report(analysis_id: str, user_id: int, report_type: str, question: str | None,
                    period: str | None = None, on_trace=None) -> tuple[str, list[dict[str, Any]]]:
    """主入口：执行完整工作流，返回 (markdown, trace)。

    on_trace: 可选回调 (stage, status, detail)，用于实时更新数据库轨迹。
    """
    trace: list[dict[str, Any]] = []

    def record(stage: str, status: str, detail: str = ""):
        entry = {"stage": stage, "status": status, "detail": detail, "time": _now()}
        trace.append(entry)
        if on_trace:
            try:
                on_trace(stage, status, detail)
            except Exception:
                pass

    # 1. Coordinator：路由（当前为轻量确定性路由，意图解析留待扩展）
    record("coordinator", "done", f"报告类型 {report_type}，周期 {period or '—'}，主题：{question or '综合'}")

    # 2. DataCollector：采集三维度数据
    record("collector", "running")
    try:
        data = collect_all(analysis_id, user_id)
        record("collector", "done", f"预测/指标/贡献度采集完成，缺口 {len(data['gaps'])} 项")
    except Exception as error:
        record("collector", "failed", str(error))
        raise

    # 3+4+5. LLM 链路（失败降级模板）
    try:
        record("analyst", "running")
        analysis = run_analyst(data, question, report_type, period)
        record("analyst", "done", f"洞察 {len(analysis.get('insights', []))} 条，风险 {len(analysis.get('risks', []))} 条，建议 {len(analysis.get('actions', []))} 条")

        record("writer", "running")
        markdown = run_writer(data, analysis, report_type, question, period)
        record("writer", "done", f"报告 {len(markdown)} 字")

        record("reviewer", "running")
        review = run_reviewer(data, markdown)
        if review.get("pass"):
            record("reviewer", "done", "审核通过")
        else:
            issues = review.get("issues", [])
            record("reviewer", "revise", f"审核发现 {len(issues)} 个问题，修订一次")
            # 单次修订：把问题反馈给 Writer 重写
            markdown = run_writer(data, analysis, report_type, question, period) if not issues else chat([
                {"role": "system", "content": prompts.WRITER_SYSTEMS.get(report_type, prompts.WRITER_SYSTEM)},
                {"role": "user", "content": (
                    f"此前报告未通过审核，问题：{json.dumps(issues, ensure_ascii=False)}\n"
                    f"分析要点：{json.dumps(analysis, ensure_ascii=False)}\n数据包：{_compact_data(data)}\n请修正问题后重写报告。"
                )},
            ], temperature=0.3)
            record("reviewer", "done", "修订完成（带审核意见交付）")
        return markdown, trace

    except LLMUnavailableError as error:
        record("llm", "degraded", f"{error} → 使用模板化简报")
        return _template_report(data, report_type, question, period), trace


def chat_answer(analysis_id: str, user_id: int, question: str) -> str:
    """AgentChat 轻量链路：采集 → 单轮 LLM 回答。"""
    data = collect_all(analysis_id, user_id)
    try:
        return chat([
            {"role": "system", "content": prompts.CHAT_SYSTEM},
            {"role": "user", "content": f"数据包：\n{_compact_data(data)}\n\n用户问题：{question}"},
        ], temperature=0.3)
    except LLMUnavailableError:
        return "AI 服务暂时不可用，请稍后重试。你可以在「Agent 报告」页面生成数据简报作为参考。"
