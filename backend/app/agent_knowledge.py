"""经营分析 Agent 的内置知识库。

把「系统是什么、有哪些模块、数据口径、景点清单」等静态知识整理成文本，
作为 LLM 的 system 背景注入；同时提供 `build_context`，把当前景点的实时数据
快照（预测/报告/归因/准确率/游客声音）拼进上下文，让 Agent 能就系统内数据
回答运营问题。
"""

from __future__ import annotations

from . import agent_tools as tools

SYSTEM_OVERVIEW = """你是「智景 ScenicMind」的 AI 经营助手，服务对象是景区管理人员和运营人员。你的任务是根据系统测算的客流数据，帮助他们了解客流情况并给出运营建议。

【系统能力】
智景 ScenicMind 基于历史客流、天气、节假日等数据，提前预测景区未来 7 天每天的入园人数，并提供：
1. 今日及未来一周的客流预测；
2. 客流变化的主要影响因素（如周末、天气、节假日等）；
3. 峰值日预警与接待压力评估；
4. 游客关注热点与反馈。

【对话风格】
- 用正常、自然的语气对话，像同事之间交流工作一样，不需要过度口语化。
- 可以正常使用专业概念，但第一次出现时简要解释一下，比如"预测准确率约 85%（MAPE 15%，即平均误差在 15% 左右）"。
- 数据该精确就精确，该概括就概括。关键数字（如人数、日期）给出具体值，背景信息可以简述。
- 结论清晰、有条理，建议分点列出。
"""


def _number(value: int | float) -> str:
    """把数字转成带千分位的大白话数字，便于肉眼阅读。"""
    return f"{value:,.0f}"


def build_context(spot: str) -> str:
    """把知识库 + 当前景点数据快照拼成一段可注入 LLM 的上下文。"""
    forecast = tools.query_forecast(spot)
    report = tools.query_report(spot)
    accuracy = tools.query_accuracy(spot)
    attribution = tools.query_attribution(spot)
    evidence = tools.query_evidence(spot)

    drivers = "；".join(
        f"{d['label']}——{'拉高' if d['direction'] == 'positive' else '拉低'}人流约 {_number(abs(d['shap']))} 人"
        for d in attribution["global"]
    )
    topics = "、".join(t["label"] for t in evidence["topTopics"])
    peak_rate = report["kpis"]["peakCapacityRate"] * 100
    accuracy_score = round((1 - accuracy["mapeDaily"]) * 100)
    today = forecast["today"]

    return (
        f"{SYSTEM_OVERVIEW}\n"
        f"\n【当前景区】{spot}\n"
        f"\n【客流预测】\n"
        f"- 今天预计来 {_number(today['predicted'])} 人"
        f"（大概率在 {_number(today['rangeLow'])}–{_number(today['rangeHigh'])} 之间），属于「{today['level']}」\n"
        f"- 未来 7 天最多的一天是 {forecast['peak']['date']}，约 {_number(forecast['peak']['value'])} 人\n"
        f"【接待压力】未来 7 天总共约 {_number(report['kpis']['forecastTotal'])} 人；"
        f"最挤的一天是 {report['kpis']['peakDate']}，约 {_number(report['kpis']['peakVisitors'])} 人，"
        f"差不多达到每天最多可接待人数的 {peak_rate:.0f}% 满\n"
        f"【预测准不准】最近预测准确度大约 {accuracy_score} 分（满分 100，越高越准）\n"
        f"【什么原因影响人流】{drivers}\n"
        f"【游客声音】共 {evidence['commentCount']} 条评论，主要关心：{topics}\n"
    )


def build_welcome(spot: str) -> str:
    """对话机器人的开场白。"""
    return (
        f"你好，我是「{spot}」的经营分析助手，可以帮你查看客流预测、影响因素和运营建议。"
    )