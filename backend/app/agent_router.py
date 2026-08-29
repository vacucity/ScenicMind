"""经营分析 Agent 意图路由——规则优先，预留 LLM 语义路由。"""

from __future__ import annotations

import re

WHATIF_PATTERNS = [
    (re.compile(r"如果|假如|万一|假设"), None),
]
RAIN_PATTERNS = [re.compile(r"下雨|降雨|雨天|暴雨")]
SURGE_PATTERNS = [re.compile(r"翻倍|爆满|活动|免票|激增|大涨|爆发")]
WEEKDAY_PATTERNS = [re.compile(r"工作日|平日|周中|非周末")]

ATTRIBUTION_KEYWORDS = ["为什么", "原因", "凭什么", "怎么会", "归因", "涨了", "跌了", "下降", "上升"]
RECOMMENDATION_KEYWORDS = ["怎么办", "建议", "应对", "措施", "方案", "怎么", "策略", "人手", "排班", "分流", "限流"]
EVIDENCE_KEYWORDS = ["游客", "评论", "吐槽", "投诉", "反馈", "声音", "原声", "网友"]
DATA_KEYWORDS = ["多少", "预测", "客流", "峰值", "今天", "明天", "未来", "几天", "趋势", "承载"]


def _has_any(text: str, patterns: list[re.Pattern]) -> bool:
    return any(p.search(text) for p in patterns)


def _whatif_scenario(text: str) -> str | None:
    if _has_any(text, RAIN_PATTERNS):
        return "rain"
    if _has_any(text, SURGE_PATTERNS):
        return "surge"
    if _has_any(text, WEEKDAY_PATTERNS):
        return "weekday"
    return None


def route(message: str) -> str:
    """返回意图：data_query / attribution / recommendation / whatif / evidence / greeting / fallback"""
    text = message.strip()
    if not text:
        return "fallback"

    if _has_any(text, [re.compile(r"^(你好|hi|hello|嗨|在吗|早上好|下午好)")]):
        return "greeting"

    # what-if 优先：带"如果"且能识别场景
    if _has_any(text, [re.compile(r"如果|假如|万一|假设")]):
        if _whatif_scenario(text) is not None:
            return "whatif"
        # 带"如果"但识别不出场景，仍归为 whatif，走 fallback 场景提示
        return "whatif"

    if _has_any(text, [re.compile(k) for k in EVIDENCE_KEYWORDS]) and not _has_any(
        text, [re.compile(k) for k in DATA_KEYWORDS]
    ):
        return "evidence"

    if _has_any(text, [re.compile(k) for k in ATTRIBUTION_KEYWORDS]):
        return "attribution"

    if _has_any(text, [re.compile(k) for k in RECOMMENDATION_KEYWORDS]):
        return "recommendation"

    if _has_any(text, [re.compile(k) for k in DATA_KEYWORDS]):
        return "data_query"

    return "fallback"
