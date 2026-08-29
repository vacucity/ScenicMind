"""经营分析 Agent 回答组装（表达层）。

默认实现为规则模板（结构化数据 → 自然语言）。
预留 LLM 表达层：未来可替换 render_* 为 LLM 生成，返回前仍走证据校验。
"""

from __future__ import annotations

from typing import Any

from . import agent_tools as tools
from .agent_contracts import ChatResponse, EvidenceRef


def _fmt(value: int) -> str:
    return f"{value:,}"


def _evidence_refs_for(recommendation: dict[str, Any]) -> list[EvidenceRef]:
    refs: list[EvidenceRef] = []
    for ref in recommendation.get("evidenceRefs", []):
        refs.append(
            EvidenceRef(
                type="voice",
                label="游客原声",
                value=ref,
                ref=ref,
            )
        )
    if not refs:
        refs.append(
            EvidenceRef(
                type="knowledge",
                label="运营知识库",
                value="内置经营建议模板",
                ref=f"KNOWLEDGE-{recommendation['category']}",
            )
        )
    return refs


def render_data_query(spot: str, message: str) -> ChatResponse:
    forecast = tools.query_forecast(spot)
    report = tools.query_report(spot)
    kpis = report["kpis"]
    today = forecast["today"]
    peak = forecast["peak"]

    reply = (
        f"{spot}今日预计入园 {_fmt(today['predicted'])} 人"
        f"（区间 {_fmt(today['rangeLow'])}–{_fmt(today['rangeHigh'])}），客流{today['level']}。\n"
        f"未来 7 天峰值 {_fmt(peak['value'])} 人，出现在 {peak['date'][5:].replace('-', '月')}日，"
        f"达到日承载量的 {round(kpis['peakCapacityRate'] * 100)}%。"
    )
    evidence = [
        EvidenceRef(type="metric", label="今日预测", value=_fmt(today["predicted"]), ref="METRIC-TODAY"),
        EvidenceRef(type="metric", label="峰值", value=_fmt(peak["value"]), ref="METRIC-PEAK"),
        EvidenceRef(type="metric", label="承载率", value=f"{round(kpis['peakCapacityRate'] * 100)}%", ref="METRIC-CAPACITY"),
    ]
    suggestions = ["本周峰值是哪天？", "为什么会达到这个峰值？", "给出应对建议"]
    return ChatResponse(
        reply=reply,
        intent="data_query",
        spot=spot,
        evidence=evidence,
        suggestions=suggestions,
        trace=_trace("rule-template"),
    )


def render_attribution(spot: str, message: str) -> ChatResponse:
    drivers = tools.query_drivers(spot)["drivers"]
    report = tools.query_report(spot)
    confidence = tools.query_drivers(spot)["confidence"]

    if not drivers:
        reply = f"{spot}当前样本不足，无法给出可靠的归因，请降低置信度预期。"
        return ChatResponse(
            reply=reply,
            intent="attribution",
            spot=spot,
            evidence=[],
            suggestions=["查看游客原声", "给出运营建议"],
            trace=_trace("rule-template"),
        )

    parts = []
    evidence: list[EvidenceRef] = []
    for driver in drivers[:3]:
        sign = "+" if driver["contribution"] >= 0 else ""
        parts.append(f"{driver['label']}（{sign}{_fmt(driver['contribution'])} 人）")
        evidence.append(
            EvidenceRef(
                type="driver",
                label=driver["label"],
                value=f"{sign}{_fmt(driver['contribution'])} 人",
                ref=f"DRIVER-{driver['feature'].upper()}",
            )
        )

    reply = (
        f"本期客流主要受以下因素影响：{'、'.join(parts)}。\n"
        f"最强驱动是「{drivers[0]['label']}」，贡献 {_fmt(drivers[0]['contribution'])} 人。"
        f"（归因置信度 {confidence}）"
    )
    return ChatResponse(
        reply=reply,
        intent="attribution",
        spot=spot,
        evidence=evidence,
        suggestions=["给出应对建议", "游客是怎么评价的？"],
        trace=_trace("rule-template"),
    )


def render_recommendation(spot: str, message: str) -> ChatResponse:
    report = tools.query_report(spot)
    recs = report["recommendations"]
    evidence: list[EvidenceRef] = []
    lines = []
    for rec in recs[:3]:
        lines.append(f"【{rec['priority']}】{rec['title']}：{rec['action']}")
        evidence.extend(_evidence_refs_for(rec))

    reply = (
        f"针对 {spot} 当前客流态势，给出 {len(recs)} 条建议，优先级从高到低：\n"
        + "\n".join(lines)
    )
    return ChatResponse(
        reply=reply,
        intent="recommendation",
        spot=spot,
        evidence=evidence,
        suggestions=["如果下雨怎么办？", "查看这些建议的依据"],
        trace=_trace("rule-template"),
    )


def render_whatif(spot: str, message: str, scenario: str | None = None) -> ChatResponse:
    from .agent_router import _whatif_scenario

    scenario = scenario or _whatif_scenario(message)
    if scenario is None:
        reply = (
            "我可以帮你做反事实推演，试试这样问：\n"
            "· 如果下周下雨，客流会怎样？\n"
            "· 如果客流翻倍呢？\n"
            "· 如果变成工作日呢？"
        )
        return ChatResponse(
            reply=reply,
            intent="whatif",
            spot=spot,
            evidence=[],
            suggestions=["如果下周下雨呢？", "如果客流翻倍呢？"],
            trace=_trace("rule-template"),
        )

    result = tools.whatif(spot, scenario)
    delta = result["delta"]
    direction = "上调" if delta > 0 else "下调"
    reply = (
        f"在「{result['scenarioLabel']}」场景下，{spot}峰值日（{result['peakDate'][5:]}）客流"
        f"预计从 {_fmt(result['baseValue'])} 人 {direction} {abs(round(result['deltaRate'] * 100))}%"
        f"至 {_fmt(result['adjustedValue'])} 人。\n"
        f"承载率风险从「{result['riskBefore']}」变为「{result['riskAfter']}」。"
    )
    evidence = [
        EvidenceRef(type="metric", label="基线峰值", value=_fmt(result["baseValue"]), ref="WHATIF-BASE"),
        EvidenceRef(type="metric", label="调整后峰值", value=_fmt(result["adjustedValue"]), ref="WHATIF-ADJUSTED"),
    ]
    suggestions = ["给出应对建议", "这种情况该怎么排班？"]
    return ChatResponse(
        reply=reply,
        intent="whatif",
        spot=spot,
        evidence=evidence,
        suggestions=suggestions,
        trace=_trace("rule-template"),
    )


def render_evidence(spot: str, message: str) -> ChatResponse:
    data = tools.query_evidence(spot)
    count = data["commentCount"]
    confidence = data["confidence"]
    low = count < 20

    top = data["topTopics"][:3]
    topics = "、".join(f"{t['label']}（{t['share'] * 100:.0f}%）" for t in top)

    head = "（样本不足，结论置信度低）" if low else ""
    reply = (
        f"共分析 {count} 条关于「{data['sampleScope']}」的高互动评论{head}。\n"
        f"游客讨论集中在：{topics}。\n"
    )
    evidence: list[EvidenceRef] = []
    for item in data["evidence"][:3]:
        reply += f"\n· {item['quote']}"
        evidence.append(
            EvidenceRef(
                type="voice",
                label=item["category"],
                value=f"影响分 {item['impactScore']}",
                ref=item["id"],
            )
        )
    return ChatResponse(
        reply=reply,
        intent="evidence",
        spot=spot,
        evidence=evidence,
        suggestions=["这些评价反映了什么经营问题？", "给出改进建议"],
        trace=_trace("rule-template"),
    )


def render_greeting(spot: str, message: str) -> ChatResponse:
    reply = (
        f"你好，我是 {spot} 的经营分析 Agent。你可以问我：\n"
        "· 今天/未来客流预测\n"
        "· 客流波动的原因\n"
        "· 该采取什么运营措施\n"
        "· 如果下雨/客流翻倍会怎样\n"
        "· 游客的真实评价"
    )
    return ChatResponse(
        reply=reply,
        intent="greeting",
        spot=spot,
        evidence=[],
        suggestions=["今天客流多少？", "给出运营建议", "游客怎么评价的？"],
        trace=_trace("rule-template"),
    )


def render_fallback(spot: str, message: str) -> ChatResponse:
    reply = (
        f"这个问题我暂时没有把握准确回答，以免误导经营决策。\n"
        f"我可以可靠地帮你：查询客流预测、解释波动原因、给出经营建议、做反事实推演、看游客原声。"
    )
    return ChatResponse(
        reply=reply,
        intent="fallback",
        spot=spot,
        evidence=[],
        suggestions=["今天客流多少？", "给出运营建议", "如果下雨怎么办？"],
        trace=_trace("rule-template"),
    )


def _trace(mode: str) -> dict[str, str | bool]:
    return {
        "agentVersion": "scenicmind-agent-v1",
        "intentSource": "rule-router",
        "generationMode": mode,
        "evidenceBound": True,
    }


RENDERERS = {
    "data_query": render_data_query,
    "attribution": render_attribution,
    "recommendation": render_recommendation,
    "whatif": render_whatif,
    "evidence": render_evidence,
    "greeting": render_greeting,
    "fallback": render_fallback,
}


def respond(intent: str, spot: str, message: str) -> ChatResponse:
    renderer = RENDERERS.get(intent, render_fallback)
    return renderer(spot, message)
