from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


# 景点显示名 -> 稳定 ID。评论数据里出现的全部景点都在此，供模块一/模块二/Agent
# 统一使用，避免同一个景点在不同接口里返回不同的 spotId。
SPOT_ID_BY_NAME: dict[str, str] = {
    "九寨沟": "jiuzhaigou",
    "黄果树瀑布": "huangguoshu",
    "贵州全域/综合": "guizhou-quanyu",
    "贵阳市区/黔灵山": "guiyang-qianlingshan",
    "西江千户苗寨": "xijiang-qianhu-miaozhai",
    "荔波小七孔": "libo-xiaoqikong",
    "梵净山": "fanjingshan",
    "遵义红色胜地/赤水": "zunyi-chishui",
    "万峰林/马岭河": "wanfenglin-malinghe",
    "织金洞": "zhijindong",
    "镇远古城/舞阳河": "zhenyuan-wuyanghe",
    "肇兴侗寨/加榜梯田": "zhaoxing-dongzhai",
    "阿西里西韭菜坪/百里杜鹃": "axilixi-bailidujuan",
    "六盘水凉都/乌蒙大草原": "liupanshui-wumeng",
}


def spot_id_for(name: str) -> str:
    """返回景点显示名对应的稳定 ID；未收录的名称原样返回。"""
    return SPOT_ID_BY_NAME.get(name, name)


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
    spot_id: str = "jiuzhaigou"
    spot_name: str = "九寨沟"
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

