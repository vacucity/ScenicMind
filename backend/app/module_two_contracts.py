from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ForecastPoint(CamelModel):
    date: date
    predicted_visitors: int = Field(ge=0)
    p90_visitors: int = Field(ge=0)
    capacity: int = Field(gt=0)
    actual_visitors: int | None = Field(default=None, ge=0)


class FeatureDriver(CamelModel):
    feature: str
    label: str
    contribution_visitors: int
    direction: Literal["positive", "negative"]
    explanation: str


class ReportRequest(CamelModel):
    spot_id: str = "huangguoshu"
    spot_name: str = "黄果树瀑布"
    period_label: str = "未来 7 天"
    capacity: int = Field(default=55_000, gt=0)
    model_version: str = "demo-ensemble-v1"
    data_snapshot: str = "demo-snapshot"
    forecast: list[ForecastPoint] = Field(default_factory=list)
    drivers: list[FeatureDriver] = Field(default_factory=list)


class KpiSummary(CamelModel):
    forecast_total: int
    peak_date: date
    peak_visitors: int
    peak_capacity_rate: float
    risk_level: Literal["低", "中", "高"]
    confidence: int = Field(ge=0, le=100)


class SentimentSlice(CamelModel):
    label: str
    count: int
    share: float


class TopicInsight(CamelModel):
    label: str
    count: int
    share: float


class CommentEvidence(CamelModel):
    evidence_id: str
    category: str
    sentiment: str
    impact_score: float
    quote: str
    source_url: str


class VisitorInsight(CamelModel):
    sample_scope: str
    comment_count: int
    confidence: Literal["低", "中", "高"]
    sentiments: list[SentimentSlice]
    top_topics: list[TopicInsight]
    evidence: list[CommentEvidence]


class Recommendation(CamelModel):
    recommendation_id: str
    priority: Literal["高", "中", "低"]
    category: str
    title: str
    action: str
    rationale: str
    expected_impact: str
    evidence_refs: list[str]
    status: Literal["待评估", "已采纳"] = "待评估"


class ReportTrace(CamelModel):
    model_version: str
    data_snapshot: str
    insight_source: str
    generation_mode: str
    prompt_version: str


class ModuleTwoReport(CamelModel):
    report_id: str
    title: str
    spot_id: str
    spot_name: str
    period_label: str
    executive_summary: str
    kpis: KpiSummary
    forecast: list[ForecastPoint]
    drivers: list[FeatureDriver]
    visitor_insight: VisitorInsight
    recommendations: list[Recommendation]
    guardrails: list[str]
    trace: ReportTrace

