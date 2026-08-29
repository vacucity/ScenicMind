from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
from chinese_calendar import get_holiday_detail, is_workday

from src.io import write_parquet_and_csv

HOLIDAY_NAME_MAP = {
    "New Year's Day": "元旦",
    "Spring Festival": "春节",
    "Tomb-sweeping Day": "清明节",
    "Labour Day": "劳动节",
    "Dragon Boat Festival": "端午节",
    "Mid-autumn Festival": "中秋节",
    "National Day": "国庆节",
}


def _holiday_parts(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    named = frame[frame["holiday_name"].notna()].copy()
    if named.empty:
        for c in ["holiday_day_index", "holiday_length", "days_until_holiday_end"]:
            frame[c] = pd.NA
        return frame
    named["block"] = (
        named["holiday_name"].ne(named["holiday_name"].shift())
        | named["date"].diff().dt.days.ne(1)
    ).cumsum()
    named["holiday_day_index"] = named.groupby("block").cumcount() + 1
    named["holiday_length"] = named.groupby("block")["date"].transform("size")
    named["days_until_holiday_end"] = named["holiday_length"] - named["holiday_day_index"]
    return frame.merge(
        named[["date", "holiday_day_index", "holiday_length", "days_until_holiday_end"]], on="date", how="left"
    )


def build(start: pd.Timestamp, end: pd.Timestamp, root: Path) -> pd.DataFrame:
    frame = pd.DataFrame({"date": pd.date_range(start, end, freq="D")})
    detail = [get_holiday_detail(d.date()) for d in frame["date"]]
    frame["holiday_name"] = [
        HOLIDAY_NAME_MAP.get(name, name) if is_holiday and name else None for is_holiday, name in detail
    ]
    frame["is_official_holiday"] = [int(bool(is_holiday and name)) for is_holiday, name in detail]
    frame["is_makeup_workday"] = [int(d.weekday() >= 5 and is_workday(d.date())) for d in frame["date"]]
    frame["is_weekend"] = frame["date"].dt.weekday.ge(5).astype("int8")
    frame["is_rest_day"] = [int(not is_workday(d.date())) for d in frame["date"]]
    frame["year"] = frame["date"].dt.year.astype("int16")
    frame["month"] = frame["date"].dt.month.astype("int8")
    frame["day"] = frame["date"].dt.day.astype("int8")
    frame["weekday"] = frame["date"].dt.weekday.astype("int8")
    frame["day_of_year"] = frame["date"].dt.dayofyear.astype("int16")
    frame["week_of_year"] = frame["date"].dt.isocalendar().week.astype("int8")
    frame["quarter"] = frame["date"].dt.quarter.astype("int8")
    frame["is_month_start"] = frame["date"].dt.is_month_start.astype("int8")
    frame["is_month_end"] = frame["date"].dt.is_month_end.astype("int8")
    frame["is_summer_vacation"] = frame["month"].isin([7, 8]).astype("int8")
    frame["is_winter_vacation"] = frame["month"].isin([1, 2]).astype("int8")
    mmdd = frame["date"].dt.strftime("%m-%d")
    frame["is_peak_season"] = mmdd.between("04-01", "11-15").astype("int8")
    frame["is_offseason"] = (1 - frame["is_peak_season"]).astype("int8")
    frame["sin_doy"] = frame["day_of_year"].map(lambda x: math.sin(2 * math.pi * x / 365.25))
    frame["cos_doy"] = frame["day_of_year"].map(lambda x: math.cos(2 * math.pi * x / 365.25))
    frame["sin_weekday"] = frame["weekday"].map(lambda x: math.sin(2 * math.pi * x / 7))
    frame["cos_weekday"] = frame["weekday"].map(lambda x: math.cos(2 * math.pi * x / 7))
    frame = _holiday_parts(frame)

    holiday_dates = frame.loc[frame["is_official_holiday"].eq(1), "date"]
    if len(holiday_dates):
        next_vals, prev_vals = [], []
        arr = holiday_dates.to_numpy()
        for d in frame["date"]:
            future = arr[arr >= d.to_datetime64()]
            past = arr[arr <= d.to_datetime64()]
            next_vals.append((pd.Timestamp(future[0]) - d).days if len(future) else pd.NA)
            prev_vals.append((d - pd.Timestamp(past[-1])).days if len(past) else pd.NA)
        frame["days_to_next_holiday"] = pd.array(next_vals, dtype="Int16")
        frame["days_since_prev_holiday"] = pd.array(prev_vals, dtype="Int16")
    frame["is_pre_holiday_1"] = frame["days_to_next_holiday"].eq(1).fillna(False).astype("int8")
    frame["is_pre_holiday_3"] = frame["days_to_next_holiday"].between(1, 3).fillna(False).astype("int8")
    frame["is_post_holiday_1"] = frame["days_since_prev_holiday"].eq(1).fillna(False).astype("int8")
    frame["is_post_holiday_3"] = frame["days_since_prev_holiday"].between(1, 3).fillna(False).astype("int8")
    write_parquet_and_csv(frame, root / "data/silver/calendar_daily.parquet")
    return frame
