from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd

from scenicmind.io import cached_get, write_parquet_and_csv


def _normalize(frame: pd.DataFrame) -> pd.DataFrame:
    columns = {str(c).strip().lower(): c for c in frame.columns}
    date_col = next((columns[k] for k in columns if k in {"date", "日期"}), None)
    visitor_col = next(
        (columns[k] for k in columns if k in {"visitors", "visitor", "客流量", "游客量", "人数"}),
        None,
    )
    if date_col is None or visitor_col is None:
        raise ValueError(f"Unexpected GitHub target schema: {list(frame.columns)}")
    out = frame[[date_col, visitor_col]].rename(columns={date_col: "date", visitor_col: "visitors"})
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
    out["visitors"] = pd.to_numeric(out["visitors"], errors="coerce")
    return out.dropna(subset=["date", "visitors"]).sort_values("date").drop_duplicates("date", keep="last")


def collect(url: str, root: Path, refresh: bool = False) -> pd.DataFrame:
    raw_path = root / "data/bronze/visitors/github_jiuzhaigou_daily.csv"
    payload = cached_get(url, raw_path, refresh=refresh, pause_seconds=0)
    try:
        frame = pd.read_csv(BytesIO(payload))
    except UnicodeDecodeError:
        frame = pd.read_csv(BytesIO(payload), encoding="gb18030")
    out = _normalize(frame)
    out["target_source"] = "github_seed"
    write_parquet_and_csv(out, root / "data/silver/target_github.parquet")
    return out

