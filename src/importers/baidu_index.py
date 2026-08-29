from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


def import_directory(directory: Path) -> pd.DataFrame | None:
    files = sorted([*directory.glob("*.csv"), *directory.glob("*.xlsx")])
    if not files:
        return None
    frames = []
    for path in files:
        frame = pd.read_csv(path) if path.suffix.lower() == ".csv" else pd.read_excel(path)
        date_col = next((c for c in frame.columns if str(c).lower() in {"date", "日期"}), None)
        if date_col is None:
            continue
        frame = frame.rename(columns={date_col: "date"})
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        for c in frame.columns:
            if c != "date":
                safe = re.sub(r"\W+", "_", str(c)).strip("_").lower()
                frame = frame.rename(columns={c: f"baidu_{safe}_raw"})
        frames.append(frame)
    if not frames:
        return None
    out = frames[0]
    for frame in frames[1:]:
        out = out.merge(frame, on="date", how="outer")
    return out.sort_values("date").drop_duplicates("date")

