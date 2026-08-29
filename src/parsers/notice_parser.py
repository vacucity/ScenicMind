from __future__ import annotations

import re
from datetime import timedelta

import pandas as pd

RULES = {
    "is_closed": ("临时闭园", "全天闭园", "实行闭园", "景区闭园", "暂停开放", "停止接待"),
    "is_reopen": ("恢复开放", "全域恢复开放"),
    "is_partial_open": ("部分开放", "部分区域", "游览调整", "季节性关闭"),
    "sold_out_flag": ("售罄", "达到最大承载量", "已达最大承载量"),
    "discount_flag": ("门票优惠", "半价", "门票减免", "优惠政策"),
    "free_ticket_flag": ("免门票", "免票", "免费开放"),
    "capacity_restricted": ("限流", "最大承载量", "限量、预约、错峰"),
}

FULL_DATE_RE = re.compile(r"(20\d{2})年(\d{1,2})月(\d{1,2})日")
MONTH_DAY_RE = re.compile(r"(?<!\d)(\d{1,2})月(\d{1,2})日")
RANGE_RE = re.compile(r"(\d{1,2})月(\d{1,2})日\s*(?:至|到|[-—~～])\s*(?:(\d{1,2})月)?(\d{1,2})日")
RESERVED_WAN_RE = re.compile(r"(?:预订|预约)[^。；，,]{0,16}?([\d.]+)\s*万(?:张|人次)")
CAPACITY_RE = re.compile(r"最大(?:游客)?承载量(?:为|是|：|:)?\s*([\d,]{4,6})\s*人次")
PRICE_RE = re.compile(r"门票(?:价格|价)?(?:为|是|：|:)?\s*(\d{2,3})\s*元")
BUS_PRICE_RE = re.compile(r"观光车(?:票|价格)?(?:为|是|：|:)?\s*(\d{2,3})\s*元")
TIME_RE = re.compile(r"入园时间(?:为|：|:)?\s*(\d{1,2}:\d{2})\s*[-—至]\s*(\d{1,2}:\d{2})")
CLOSE_TIME_RE = re.compile(r"闭园时间(?:为|：|:)?\s*(\d{1,2}:\d{2})")


def classify(text: str) -> dict[str, int]:
    flags = {name: int(any(term in text for term in terms)) for name, terms in RULES.items()}
    # “闭园时间 18:00”是正常营业时间说明，不代表当天闭园。
    if flags["is_closed"] and not any(
        term in text for term in ("临时闭园", "全天闭园", "实行闭园", "景区闭园", "暂停开放", "停止接待")
    ):
        flags["is_closed"] = 0
    return flags


def _infer_year(published: pd.Timestamp, month: int, day: int) -> pd.Timestamp | None:
    for year in (published.year, published.year + 1, published.year - 1):
        try:
            candidate = pd.Timestamp(year=year, month=month, day=day)
        except ValueError:
            continue
        if abs((candidate - published.normalize()).days) <= 180:
            return candidate
    return None


def event_dates(text: str, published: pd.Timestamp, sold_out: bool) -> list[pd.Timestamp]:
    dates: set[pd.Timestamp] = set()
    for y, m, d in FULL_DATE_RE.findall(text):
        try:
            candidate = pd.Timestamp(year=int(y), month=int(m), day=int(d))
            if abs((candidate - published.normalize()).days) <= 365:
                dates.add(candidate)
        except ValueError:
            pass
    for m1, d1, m2, d2 in RANGE_RE.findall(text):
        start = _infer_year(published, int(m1), int(d1))
        if start is None:
            continue
        end_month = int(m2) if m2 else int(m1)
        end = _infer_year(start, end_month, int(d2))
        if end is None or end < start or (end - start).days > 31:
            continue
        cur = start
        while cur <= end:
            dates.add(cur)
            cur += timedelta(days=1)
    for m, d in MONTH_DAY_RE.findall(text):
        candidate = _infer_year(published, int(m), int(d))
        if candidate is not None:
            dates.add(candidate)
    if sold_out:
        future = sorted(d for d in dates if -1 <= (d - published.normalize()).days <= 60)
        if future:
            return future
    return sorted(dates) if dates else [published.normalize()]


def parse_notice(record: dict) -> list[dict]:
    published = pd.Timestamp(record["published_at"])
    text = f"{record['title']}\n{record['text']}"
    flags = classify(text)
    title_flags = classify(record["title"])
    # Operational/promotion labels favor title precision. Article boilerplate
    # often repeats normal closing hours, substitute offers, or generic policy
    # language that must not label the notice event itself.
    for name in ["is_closed", "is_reopen", "is_partial_open", "discount_flag", "free_ticket_flag"]:
        flags[name] = title_flags[name]
    sold_out = bool(flags["sold_out_flag"])
    reserved = None
    m = RESERVED_WAN_RE.search(text)
    if m:
        reserved = int(float(m.group(1)) * 10000)
    capacity = None
    m = CAPACITY_RE.search(text)
    if m:
        capacity = int(m.group(1).replace(",", ""))
    if sold_out and reserved is None and capacity is not None:
        reserved = capacity
    price = int(m.group(1)) if (m := PRICE_RE.search(text)) else None
    bus_price = int(m.group(1)) if (m := BUS_PRICE_RE.search(text)) else None
    open_hour = last_entry_hour = close_hour = None
    if m := TIME_RE.search(text):
        open_hour, last_entry_hour = m.group(1), m.group(2)
    if m := CLOSE_TIME_RE.search(text):
        close_hour = m.group(1)
    dates = event_dates(text, published, sold_out)
    rows = []
    for event_date in dates:
        lead_days = (event_date - published.normalize()).days
        rows.append(
            {
                "event_date": event_date,
                "available_at": published.tz_localize("Asia/Shanghai") if published.tzinfo is None else published,
                "published_at": published,
                "source_url": record["url"],
                "title": record["title"],
                **flags,
                "known_reserved_count": reserved,
                "daily_capacity": capacity,
                "ticket_price": price,
                "bus_price": bus_price,
                "open_hour": open_hour,
                "last_entry_hour": last_entry_hour,
                "close_hour": close_hour,
                "sold_out_notice_lead_days": lead_days if sold_out else None,
                "parser_confidence": "high" if sold_out and 0 <= lead_days <= 60 else "medium",
            }
        )
    return rows
