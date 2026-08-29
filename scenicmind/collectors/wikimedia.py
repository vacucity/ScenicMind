from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

import pandas as pd

from scenicmind.io import cached_get, write_parquet_and_csv


def _chunks(start: pd.Timestamp, end: pd.Timestamp):
    for year in range(start.year, end.year + 1):
        yield max(start, pd.Timestamp(year=year, month=1, day=1)), min(end, pd.Timestamp(year=year, month=12, day=31))


def _collect_article(endpoint: str, project: str, article: str, prefix: str, root: Path, start, end, refresh):
    pieces = []
    for a, b in _chunks(start, end):
        url = (
            f"{endpoint}/{project}/all-access/user/{quote(article, safe='')}/daily/"
            f"{a.strftime('%Y%m%d')}/{b.strftime('%Y%m%d')}"
        )
        payload = cached_get(url, root / f"data/bronze/wikipedia/{prefix}_{a.year}.json", refresh=refresh, pause_seconds=0.1)
        obj = json.loads(payload)
        rows = [
            {"date": pd.to_datetime(item["timestamp"][:8], format="%Y%m%d"), f"wiki_{prefix}_views": item["views"]}
            for item in obj.get("items", [])
        ]
        pieces.append(pd.DataFrame(rows))
    return pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame(columns=["date", f"wiki_{prefix}_views"])


def collect(endpoint: str, root: Path, start: pd.Timestamp, end: pd.Timestamp, refresh: bool = False) -> pd.DataFrame:
    zh = _collect_article(endpoint, "zh.wikipedia.org", "九寨沟", "zh", root, start, end, refresh)
    en = _collect_article(endpoint, "en.wikipedia.org", "Jiuzhaigou", "en", root, start, end, refresh)
    out = zh.merge(en, on="date", how="outer").sort_values("date")
    write_parquet_and_csv(out, root / "data/silver/wikipedia_daily.parquet")
    return out

