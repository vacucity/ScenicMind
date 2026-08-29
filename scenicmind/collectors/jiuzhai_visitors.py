from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
from lxml import html

from scenicmind.io import cached_get, write_parquet_and_csv

VISITOR_RE = re.compile(r"(?:今日)?共接待\s*([\d,]+)\s*人次|接待游客\s*([\d,]+)\s*人次")
DATE_RE = re.compile(r"(20\d{2})[-年/](\d{1,2})[-月/](\d{1,2})日?")
TOTAL_PAGES_RE = re.compile(r"共\s*(\d+)\s*页")


def parse_visitor_count(text: str) -> int | None:
    m = VISITOR_RE.search(text.replace("，", ","))
    if not m:
        return None
    return int((m.group(1) or m.group(2)).replace(",", ""))


def _date_from(text: str, href: str) -> pd.Timestamp | None:
    for candidate in (text, href):
        m = DATE_RE.search(candidate)
        if m:
            try:
                return pd.Timestamp(year=int(m.group(1)), month=int(m.group(2)), day=int(m.group(3)))
            except ValueError:
                pass
    return None


def parse_listing(payload: bytes, base_url: str) -> tuple[list[dict], int | None]:
    doc = html.fromstring(payload)
    page_text = " ".join(doc.xpath("//text()"))
    page_match = TOTAL_PAGES_RE.search(page_text)
    total_pages = int(page_match.group(1)) if page_match else None
    records: list[dict] = []
    seen: set[str] = set()
    for anchor in doc.xpath("//a[contains(@href, '/news/number-of-tourists/')]"):
        href = urljoin(base_url, anchor.get("href") or "")
        title = " ".join(t.strip() for t in anchor.xpath(".//text()") if t.strip())
        count = parse_visitor_count(title)
        if count is None or href in seen:
            continue
        seen.add(href)
        context = " ".join(anchor.xpath("ancestor::tr[1]//text()") or anchor.xpath("parent::*//text()"))
        date = _date_from(context, href)
        if date is None:
            continue
        records.append(
            {
                "date": date,
                "visitors": count,
                "source_url": href,
                "published_at": date,
                "collected_at": pd.Timestamp(datetime.now(timezone.utc)),
                "raw_title": title,
                "raw_text": title,
                "target_quality": "official_listing",
            }
        )
    return records, total_pages


def collect(base_url: str, root: Path, start_date: str, refresh: bool = False) -> pd.DataFrame:
    all_records: list[dict] = []
    page = 0
    total_pages: int | None = None
    cutoff = pd.Timestamp(start_date)
    while total_pages is None or page < total_pages:
        offset = page * 20
        url = f"{base_url}?start={offset}"
        payload = cached_get(url, root / f"data/bronze/visitors/list_{offset:05d}.html", refresh=refresh)
        records, discovered_pages = parse_listing(payload, base_url)
        if total_pages is None and discovered_pages:
            total_pages = discovered_pages
        if not records:
            break
        all_records.extend(records)
        oldest = min(r["date"] for r in records)
        if oldest < cutoff and page > 0:
            break
        page += 1

    if not all_records:
        raise RuntimeError("Official visitor listing returned no parseable records")
    frame = pd.DataFrame(all_records).sort_values(["date", "collected_at"])
    frame = frame.drop_duplicates("date", keep="last")
    frame = frame[frame["date"] >= cutoff].reset_index(drop=True)
    write_parquet_and_csv(frame, root / "data/silver/target_official.parquet")
    return frame


def merge_targets(github: pd.DataFrame, official: pd.DataFrame, root: Path) -> pd.DataFrame:
    g = github[["date", "visitors"]].rename(columns={"visitors": "visitors_github"})
    o = official[["date", "visitors", "source_url", "published_at", "target_quality"]].rename(
        columns={"visitors": "visitors_official"}
    )
    merged = g.merge(o, on="date", how="outer")
    merged["target_conflict"] = (
        merged["visitors_github"].notna()
        & merged["visitors_official"].notna()
        & (merged["visitors_github"] != merged["visitors_official"])
    ).astype("int8")
    merged["visitors"] = merged["visitors_official"].combine_first(merged["visitors_github"])
    merged["target_source"] = merged["visitors_official"].notna().map({True: "jiuzhai_official", False: "github_seed"})
    merged["target_quality"] = merged["target_quality"].fillna("official_derived_github_seed")
    merged = merged.sort_values("date").reset_index(drop=True)

    conflicts = merged.loc[merged["target_conflict"].eq(1), ["date", "visitors_github", "visitors_official", "source_url"]]
    (root / "reports").mkdir(parents=True, exist_ok=True)
    conflicts.to_csv(root / "reports/target_conflicts.csv", index=False, encoding="utf-8-sig")

    spine = pd.DataFrame({"date": pd.date_range(merged["date"].min(), merged["date"].max(), freq="D")})
    out = spine.merge(merged, on="date", how="left")
    out["target_missing"] = out["visitors"].isna().astype("int8")
    out["visitors"] = out["visitors"].astype("Int64")
    write_parquet_and_csv(out, root / "data/silver/target_daily.parquet")
    return out

