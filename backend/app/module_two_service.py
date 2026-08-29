import csv
import os
from collections import Counter
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

from .module_two_contracts import (
    CommentEvidence,
    FeatureDriver,
    ForecastPoint,
    KpiSummary,
    ModuleTwoReport,
    Recommendation,
    ReportRequest,
    ReportTrace,
    SentimentSlice,
    TopicInsight,
    VisitorInsight,
)


DATASET_RELATIVE_PATH = Path(
    "datasets/bilibili_guizhou_travel_comments/guizhou_travel_comments_cleaned_ge10likes.csv"
)
SENTIMENT_ORDER = (
    "客观探讨/咨询互动",
    "强力种草/惊艳好评",
    "避坑预警/痛点吐槽",
    "实战攻略/避坑技巧",
)


def _dataset_path() -> Path:
    configured = os.getenv("SCENICMIND_COMMENTS_CSV")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / DATASET_RELATIVE_PATH


@lru_cache(maxsize=2)
def _read_comments(path: str) -> tuple[dict[str, str], ...]:
    dataset = Path(path)
    if not dataset.exists():
        return ()
    with dataset.open("r", encoding="utf-8-sig", newline="") as handle:
        return tuple(csv.DictReader(handle))


def list_spots() -> list[str]:
    rows = _read_comments(str(_dataset_path()))
    counts = Counter(row.get("primary_spot", "").strip() for row in rows)
    counts.pop("", None)
    ordered = [name for name, _ in counts.most_common() if name != "贵州全域/综合"]
    return ordered + (["贵州全域/综合"] if counts.get("贵州全域/综合") else [])


def _demo_forecast(capacity: int) -> list[ForecastPoint]:
    start = date.today() + timedelta(days=1)
    visitors = (26_500, 28_800, 31_500, 33_800, 42_100, 47_600, 35_900)
    return [
        ForecastPoint(
            date=start + timedelta(days=index),
            predicted_visitors=value,
            p90_visitors=min(capacity, round(value * 1.14)),
            capacity=capacity,
        )
        for index, value in enumerate(visitors)
    ]


def _demo_drivers() -> list[FeatureDriver]:
    return [
        FeatureDriver(
            feature="reservation_velocity",
            label="预约增速",
            contribution_visitors=6_300,
            direction="positive",
            explanation="近 72 小时预约增速高于常态，是本期最强拉升因素。",
        ),
        FeatureDriver(
            feature="weekend",
            label="周末效应",
            contribution_visitors=4_200,
            direction="positive",
            explanation="周末出游需求推高峰值日客流。",
        ),
        FeatureDriver(
            feature="rain_probability",
            label="降雨概率",
            contribution_visitors=-2_800,
            direction="negative",
            explanation="午后降雨概率抑制临时到访与户外停留。",
        ),
        FeatureDriver(
            feature="search_heat",
            label="搜索热度",
            contribution_visitors=1_700,
            direction="positive",
            explanation="目的地搜索热度连续上升，带来额外自然客流。",
        ),
    ]


def _shorten(text: str, limit: int = 118) -> str:
    normalized = " ".join(text.replace("\u00a0", " ").split())
    return normalized if len(normalized) <= limit else f"{normalized[:limit]}…"


def _visitor_insight(spot_name: str) -> VisitorInsight:
    all_rows = _read_comments(str(_dataset_path()))
    rows = tuple(row for row in all_rows if row.get("primary_spot", "").strip() == spot_name)
    scope = spot_name
    if not rows:
        rows = all_rows
        scope = "贵州全域/综合（景点样本不足，已扩大范围）"

    total = len(rows)
    sentiment_counts = Counter(row.get("sentiment", "未标注") for row in rows)
    sentiments = [
        SentimentSlice(
            label=label,
            count=sentiment_counts[label],
            share=round(sentiment_counts[label] / total, 4) if total else 0,
        )
        for label in SENTIMENT_ORDER
        if sentiment_counts[label]
    ]

    topic_counts = Counter(row.get("primary_level1", "未分类") for row in rows)
    top_topics = [
        TopicInsight(label=label, count=count, share=round(count / total, 4) if total else 0)
        for label, count in topic_counts.most_common(5)
    ]

    def evidence_rank(row: dict[str, str]) -> tuple[int, float]:
        actionable = row.get("sentiment") in {"避坑预警/痛点吐槽", "实战攻略/避坑技巧"}
        try:
            impact = float(row.get("impact_score") or 0)
        except ValueError:
            impact = 0
        return (1 if actionable else 0, impact)

    evidence: list[CommentEvidence] = []
    seen_categories: set[str] = set()
    for row in sorted(rows, key=evidence_rank, reverse=True):
        category = row.get("primary_level1", "未分类")
        if category in seen_categories and len(evidence) < 3:
            continue
        try:
            impact = float(row.get("impact_score") or 0)
        except ValueError:
            impact = 0
        evidence.append(
            CommentEvidence(
                evidence_id=f"VOICE-{len(evidence) + 1:02d}",
                category=category,
                sentiment=row.get("sentiment", "未标注"),
                impact_score=round(impact, 2),
                quote=_shorten(row.get("content", "")),
                source_url=row.get("video_url", ""),
            )
        )
        seen_categories.add(category)
        if len(evidence) == 4:
            break

    confidence = "高" if total >= 60 else "中" if total >= 20 else "低"
    return VisitorInsight(
        sample_scope=scope,
        comment_count=total,
        confidence=confidence,
        sentiments=sentiments,
        top_topics=top_topics,
        evidence=evidence,
    )


def _evidence_refs(insight: VisitorInsight, category_keyword: str | None = None) -> list[str]:
    candidates = insight.evidence
    if category_keyword:
        matched = [item for item in candidates if category_keyword in item.category]
        if matched:
            candidates = matched
    return [item.evidence_id for item in candidates[:2]]


def _recommendations(
    kpis: KpiSummary,
    drivers: list[FeatureDriver],
    insight: VisitorInsight,
) -> list[Recommendation]:
    recommendations: list[Recommendation] = []
    if kpis.peak_capacity_rate >= 0.75:
        recommendations.append(
            Recommendation(
                recommendation_id="ADV-FLOW-01",
                priority="高" if kpis.peak_capacity_rate >= 0.85 else "中",
                category="客流组织",
                title="峰值日前置启用三级分流",
                action=(
                    f"在 {kpis.peak_date:%m月%d日} 10:00 前增开 2 组入口核验与 1 组机动引导；"
                    "当实时入园量达到承载量 75% 时启动分时预约提醒，85% 时限制现场售票。"
                ),
                rationale=f"峰值预测 {kpis.peak_visitors:,} 人，预计达到日承载量的 {kpis.peak_capacity_rate:.0%}。",
                expected_impact="高峰排队时长预计下降 15%–25%",
                evidence_refs=_evidence_refs(insight, "景区运营"),
            )
        )

    if any(driver.feature == "rain_probability" and driver.contribution_visitors < 0 for driver in drivers):
        rain = next(driver for driver in drivers if driver.feature == "rain_probability")
        recommendations.append(
            Recommendation(
                recommendation_id="ADV-RAIN-02",
                priority="中",
                category="天气响应",
                title="把降雨影响转化为室内承接方案",
                action="提前发布雨天路线，在游客中心、观景平台入口增设防滑与雨具点位，并将餐饮、文创优惠券定向推送给已预约游客。",
                rationale=f"降雨对本期预测贡献为 {rain.contribution_visitors:,} 人，临时退改风险上升。",
                expected_impact="降低临时退票，提升雨天停留时长与二次消费",
                evidence_refs=_evidence_refs(insight),
            )
        )

    topic_labels = {topic.label for topic in insight.top_topics}
    if "交通自驾与行程路况" in topic_labels or "景区运营与排队管理" in topic_labels:
        recommendations.append(
            Recommendation(
                recommendation_id="ADV-TRANSIT-03",
                priority="中",
                category="交通接驳",
                title="将排队信息前移到游客抵达之前",
                action="在停车场入口和官方渠道同步发布摆渡等待时间；峰值日前一晚向预约游客推送推荐到达时段与备用停车区。",
                rationale="游客声音中，排队与交通信息不透明是最具行动价值的体验风险之一。",
                expected_impact="减少入口聚集与无效等待，降低现场咨询压力",
                evidence_refs=_evidence_refs(insight, "交通"),
            )
        )

    recommendations.append(
        Recommendation(
            recommendation_id="ADV-VOICE-04",
            priority="中",
            category="游客体验",
            title="建立高影响评论的 24 小时响应闭环",
            action="每天筛选影响力最高的 10 条评论，按价格、排队、交通、服务四类指派责任人；次日看板展示处理状态与重复问题趋势。",
            rationale=f"当前报告分析了 {insight.comment_count} 条与“{insight.sample_scope}”相关的高互动评论。",
            expected_impact="把零散舆情转化为可追踪的现场改进事项",
            evidence_refs=_evidence_refs(insight),
        )
    )
    return recommendations[:5]


def build_report(request: ReportRequest | None = None) -> ModuleTwoReport:
    request = request or ReportRequest()
    forecast = request.forecast or _demo_forecast(request.capacity)
    drivers = request.drivers or _demo_drivers()
    peak = max(forecast, key=lambda item: item.predicted_visitors)
    peak_rate = peak.predicted_visitors / peak.capacity
    risk_level = "高" if peak_rate >= 0.9 else "中" if peak_rate >= 0.75 else "低"
    insight = _visitor_insight(request.spot_name)
    confidence = min(96, 72 + min(insight.comment_count, 120) // 5)
    kpis = KpiSummary(
        forecast_total=sum(item.predicted_visitors for item in forecast),
        peak_date=peak.date,
        peak_visitors=peak.predicted_visitors,
        peak_capacity_rate=round(peak_rate, 4),
        risk_level=risk_level,
        confidence=confidence,
    )

    recommendations = _recommendations(kpis, drivers, insight)
    leading_driver = max(drivers, key=lambda item: abs(item.contribution_visitors))
    executive_summary = (
        f"{request.period_label}预计接待 {kpis.forecast_total:,} 人次，峰值出现在"
        f"{kpis.peak_date:%m月%d日}，达到承载量的 {kpis.peak_capacity_rate:.0%}。"
        f"主要驱动因素为{leading_driver.label}（{leading_driver.contribution_visitors:+,} 人）；"
        f"建议优先落实“{recommendations[0].title}”。"
    )
    report_id = f"RPT-{request.spot_id.upper()}-{date.today():%Y%m%d}"
    snapshot = request.data_snapshot
    if not request.forecast and snapshot == "demo-snapshot":
        snapshot = f"demo-{date.today():%Y%m%d}"

    return ModuleTwoReport(
        report_id=report_id,
        title=f"{request.spot_name}经营决策周报",
        spot_id=request.spot_id,
        spot_name=request.spot_name,
        period_label=request.period_label,
        executive_summary=executive_summary,
        kpis=kpis,
        forecast=forecast,
        drivers=drivers,
        visitor_insight=insight,
        recommendations=recommendations,
        guardrails=[
            "客流数字仅来自模块一输入；未接入模块一时使用明确标记的演示预测。",
            "所有游客声音均保留证据编号和原视频链接，不以单条评论代表总体游客。",
            "建议为经营决策参考，不自动控制闸机、售票、排班或现场设施。",
        ],
        trace=ReportTrace(
            model_version=request.model_version,
            data_snapshot=snapshot,
            insight_source=DATASET_RELATIVE_PATH.as_posix(),
            generation_mode="evidence-bound-rule-agent",
            prompt_version="scenicmind-module2-v1",
        ),
    )

