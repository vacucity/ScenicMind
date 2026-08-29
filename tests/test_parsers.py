import pandas as pd

from scenicmind.collectors.jiuzhai_visitors import parse_visitor_count
from scenicmind.parsers.notice_parser import parse_notice


def test_visitor_regex_variants():
    assert parse_visitor_count("九寨沟景区共接待19,906人次") == 19906
    assert parse_visitor_count("今日共接待 22033 人次") == 22033
    assert parse_visitor_count("接待游客 5000 人次") == 5000


def test_notice_sold_out_event_date_and_capacity():
    rows = parse_notice(
        {
            "title": "九寨沟景区8月14日门票预约已达最大承载量的通告",
            "published_at": pd.Timestamp("2026-08-13"),
            "text": "景区2026年8月14日门票预约已达最大承载量，旺季最大游客承载量为41000人次/天。",
            "url": "https://example.invalid/notice",
        }
    )
    row = next(r for r in rows if r["event_date"] == pd.Timestamp("2026-08-14"))
    assert row["sold_out_flag"] == 1
    assert row["known_reserved_count"] == 41000
    assert row["sold_out_notice_lead_days"] == 1


def test_normal_closing_hour_is_not_full_closure():
    rows = parse_notice(
        {
            "title": "旺季接待通告",
            "published_at": pd.Timestamp("2026-03-23"),
            "text": "入园时间为7:30-14:00，闭园时间：18:00。",
            "url": "https://example.invalid/hours",
        }
    )
    assert all(row["is_closed"] == 0 for row in rows)
