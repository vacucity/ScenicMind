from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup
from lxml import html

from scenicmind.io import cached_get, write_parquet_and_csv
from scenicmind.parsers.notice_parser import parse_notice

DATE_RE = re.compile(r"(20\d{2})[-年/](\d{1,2})[-月/](\d{1,2})日?")
TOTAL_PAGES_RE = re.compile(r"共\s*(\d+)\s*页")


def parse_listing(payload: bytes, base_url: str) -> tuple[list[dict], int | None]:
    doc = html.fromstring(payload)
    page_text = " ".join(doc.xpath("//text()"))
    m = TOTAL_PAGES_RE.search(page_text)
    total_pages = int(m.group(1)) if m else None
    rows, seen = [], set()
    for anchor in doc.xpath("//a[contains(@href, '/news/notice/')]"):
        href = urljoin(base_url, anchor.get("href") or "")
        if href in seen:
            continue
        title = " ".join(t.strip() for t in anchor.xpath(".//text()") if t.strip())
        if not title:
            continue
        context = " ".join(anchor.xpath("ancestor::tr[1]//text()") or anchor.xpath("parent::*//text()"))
        dm = DATE_RE.search(context) or DATE_RE.search(href)
        if not dm:
            continue
        seen.add(href)
        rows.append(
            {
                "title": title,
                "url": href,
                "published_at": pd.Timestamp(year=int(dm.group(1)), month=int(dm.group(2)), day=int(dm.group(3))),
            }
        )
    return rows, total_pages


def _article_text(payload: bytes) -> str:
    soup = BeautifulSoup(payload, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    article = soup.select_one("[itemprop='articleBody'], article, .item-page, .article") or soup.body or soup
    return "\n".join(line.strip() for line in article.get_text("\n").splitlines() if line.strip())


def collect(base_url: str, root: Path, refresh: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    listings: list[dict] = []
    page = 0
    total_pages = None
    while total_pages is None or page < total_pages:
        offset = page * 20
        payload = cached_get(base_url + f"?start={offset}", root / f"data/bronze/notices/list_{offset:04d}.html", refresh=refresh)
        rows, discovered = parse_listing(payload, base_url)
        if total_pages is None and discovered:
            total_pages = discovered
        if not rows:
            break
        listings.extend(rows)
        page += 1

    article_rows = []
    for idx, item in enumerate({r["url"]: r for r in listings}.values()):
        slug = re.sub(r"[^0-9A-Za-z_-]+", "_", item["url"].rstrip("/").split("/")[-1])
        try:
            payload = cached_get(item["url"], root / f"data/bronze/notices/articles/{slug}.html", refresh=refresh)
            article_rows.append({**item, "text": _article_text(payload)})
        except Exception as exc:
            article_rows.append({**item, "text": "", "fetch_error": str(exc)})
    raw = pd.DataFrame(article_rows).sort_values("published_at").drop_duplicates("url")
    write_parquet_and_csv(raw, root / "data/silver/notices_raw.parquet")

    events = []
    failures = []
    for record in raw.to_dict("records"):
        try:
            events.extend(parse_notice(record))
        except Exception as exc:
            failures.append({"url": record["url"], "title": record["title"], "error": str(exc)})
    event_frame = pd.DataFrame(events)
    if not event_frame.empty:
        event_frame = event_frame.sort_values(["event_date", "available_at", "source_url"]).reset_index(drop=True)
    write_parquet_and_csv(event_frame, root / "data/silver/notice_events.parquet")
    pd.DataFrame(failures, columns=["url", "title", "error"]).to_csv(
        root / "reports/notice_parse_failures.csv", index=False, encoding="utf-8-sig"
    )
    return raw, event_frame
