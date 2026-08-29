from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from scenicmind.io import write_parquet_and_csv

TARGET_LAGS = [1, 2, 3, 7, 14, 28, 365]
ROLL_WINDOWS = [3, 7, 14, 28]


def add_target_history(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy().sort_values("date").reset_index(drop=True)
    for lag in TARGET_LAGS:
        out[f"visitors_lag_{lag}"] = out["visitors"].shift(lag)
    past = out["visitors"].shift(1)
    for window in ROLL_WINDOWS:
        out[f"visitors_roll_mean_{window}"] = past.rolling(window, min_periods=window).mean()
    out["visitors_roll_median_7"] = past.rolling(7, min_periods=7).median()
    for window in [7, 14]:
        out[f"visitors_roll_std_{window}"] = past.rolling(window, min_periods=window).std()
    out["visitors_roll_min_7"] = past.rolling(7, min_periods=7).min()
    out["visitors_roll_max_7"] = past.rolling(7, min_periods=7).max()
    out["visitors_roll_q25_14"] = past.rolling(14, min_periods=14).quantile(0.25)
    out["visitors_roll_q75_14"] = past.rolling(14, min_periods=14).quantile(0.75)
    out["visitors_trend_strength"] = out["visitors_roll_mean_7"] / out["visitors_roll_mean_28"].replace(0, np.nan)
    out["visitors_lag1_vs_ma7"] = out["visitors_lag_1"] / out["visitors_roll_mean_7"].replace(0, np.nan)
    out["visitors_lag7_vs_ma28"] = out["visitors_lag_7"] / out["visitors_roll_mean_28"].replace(0, np.nan)
    return out


def add_weather_features(weather: pd.DataFrame, heavy_rain_mm: float, cold_c: float, heat_c: float) -> pd.DataFrame:
    out = weather.copy().sort_values("date")
    out["actual_temp_range"] = out["actual_temp_max"] - out["actual_temp_min"]
    out["actual_is_rain"] = out["actual_precipitation_sum"].gt(0).astype("int8")
    out["actual_is_heavy_rain"] = out["actual_precipitation_sum"].ge(heavy_rain_mm).astype("int8")
    out["actual_is_snow"] = out["actual_snowfall_sum"].gt(0).astype("int8")
    out["actual_is_extreme_cold"] = out["actual_temp_min"].le(cold_c).astype("int8")
    out["actual_is_extreme_heat"] = out["actual_temp_max"].ge(heat_c).astype("int8")
    out["actual_rain_3d_sum"] = out["actual_rain_sum"].rolling(3, min_periods=1).sum()
    out["actual_rain_7d_sum"] = out["actual_rain_sum"].rolling(7, min_periods=1).sum()
    out["actual_bad_weather_flag"] = (
        out[["actual_is_heavy_rain", "actual_is_snow", "actual_is_extreme_cold", "actual_is_extreme_heat"]]
        .max(axis=1)
        .astype("int8")
    )
    return out


def add_attention_features(wiki: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    explanatory = wiki.copy().sort_values("date")
    safe = wiki[["date"]].copy()
    for col in [c for c in wiki.columns if c.endswith("_views")]:
        shifted = wiki[col].shift(1)
        safe[f"{col}_lag1"] = shifted
        safe[f"{col}_lag7"] = wiki[col].shift(7)
        safe[f"{col}_ma7"] = shifted.rolling(7, min_periods=7).mean()
        safe[f"{col}_ma14"] = shifted.rolling(14, min_periods=14).mean()
        safe[f"{col}_growth7"] = shifted / wiki[col].shift(8).replace(0, np.nan) - 1
    return explanatory, safe


def _aggregate_notice_events(events: pd.DataFrame, date_spine: pd.Series, forecast_safe: bool) -> pd.DataFrame:
    dates = pd.DataFrame({"date": date_spine})
    if events is None or events.empty:
        return dates
    flags = [
        "sold_out_flag",
        "is_closed",
        "is_reopen",
        "is_partial_open",
        "discount_flag",
        "free_ticket_flag",
        "capacity_restricted",
    ]
    rows = []
    for date in dates["date"]:
        subset = events[events["event_date"].eq(date)]
        if forecast_safe:
            origin = (date - pd.Timedelta(days=1)).tz_localize("Asia/Shanghai") + pd.Timedelta(hours=23, minutes=59)
            subset = subset[subset["available_at"] <= origin]
        if subset.empty:
            rows.append({"date": date, **{c: 0 for c in flags}, "official_notice_count": 0})
            continue
        row = {"date": date, "official_notice_count": len(subset)}
        for c in flags:
            row[c] = int(subset[c].fillna(0).max()) if c in subset else 0
        for c in ["known_reserved_count", "daily_capacity"]:
            if c in subset and subset[c].notna().any():
                row[c] = subset[c].dropna().iloc[-1]
        if "sold_out_notice_lead_days" in subset and subset["sold_out_notice_lead_days"].notna().any():
            row["sold_out_notice_lead_days"] = subset["sold_out_notice_lead_days"].dropna().max()
        rows.append(row)
    out = pd.DataFrame(rows)
    if {"known_reserved_count", "daily_capacity"}.issubset(out.columns):
        out["booking_pressure_ratio"] = out["known_reserved_count"] / out["daily_capacity"].replace(0, np.nan)
    return out


def add_transport(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    hsr = pd.Timestamp("2024-08-30")
    expressway = pd.Timestamp("2025-09-28")
    out["huanglong_jiuzhai_hsr_open"] = out["date"].ge(hsr).astype("int8")
    out["days_since_hsr_open"] = (out["date"] - hsr).dt.days.clip(lower=0)
    out["jiuzhai_mianyang_expressway_open"] = out["date"].ge(expressway).astype("int8")
    out["days_since_expressway_open"] = (out["date"] - expressway).dt.days.clip(lower=0)
    return out


def _quality_fields(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    feature_cols = [c for c in out.columns if c not in {"date", "visitors", "source_url", "published_at"}]
    out["feature_missing_count"] = out[feature_cols].isna().sum(axis=1).astype("int16")
    out["quality_score"] = (1 - out["feature_missing_count"] / max(len(feature_cols), 1)).clip(0, 1)
    return out


def build_gold(
    root: Path,
    target: pd.DataFrame,
    calendar: pd.DataFrame,
    weather: pd.DataFrame,
    wiki: pd.DataFrame,
    notices: pd.DataFrame | None,
    thresholds: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    target_columns = [
        c
        for c in ["date", "visitors", "target_source", "target_quality", "target_conflict", "target_missing"]
        if c in target.columns
    ]
    base = add_target_history(target[target_columns]).merge(calendar, on="date", how="left")
    base = add_transport(base)
    weather_features = add_weather_features(
        weather,
        thresholds["heavy_rain_mm"],
        thresholds["extreme_cold_c"],
        thresholds["extreme_heat_c"],
    )
    wiki_expl, wiki_safe = add_attention_features(wiki)
    notice_expl = _aggregate_notice_events(notices, base["date"], forecast_safe=False)
    notice_safe = _aggregate_notice_events(notices, base["date"], forecast_safe=True)

    explanatory = base.merge(weather_features, on="date", how="left").merge(wiki_expl, on="date", how="left")
    explanatory = explanatory.merge(notice_expl, on="date", how="left")
    explanatory = _quality_fields(explanatory)

    safe = base.merge(wiki_safe, on="date", how="left").merge(notice_safe, on="date", how="left")
    safe = _quality_fields(safe)

    write_parquet_and_csv(
        explanatory,
        root / "data/gold/jiuzhaigou_daily_explanatory.parquet",
        root / "data/gold/jiuzhaigou_daily.csv",
    )
    write_parquet_and_csv(safe, root / "data/gold/jiuzhaigou_daily_forecast_safe_h1.parquet")
    build_feature_dictionary(root, explanatory, safe)
    return explanatory, safe


def build_feature_dictionary(root: Path, explanatory: pd.DataFrame, safe: pd.DataFrame) -> pd.DataFrame:
    rows = []
    safe_cols = set(safe.columns)
    for col in explanatory.columns:
        if col.startswith("actual_"):
            category, source, rule = "actual_weather", "Open-Meteo Archive API", "Known after event date; explanatory only"
        elif col.startswith("wiki_"):
            category, source, rule = "attention", "Wikimedia Pageviews API", "Same-day value is explanatory only; shifted variants are T-1 safe"
        elif col.startswith("visitors_"):
            category, source, rule = "historical_target", "Jiuzhaigou official/GitHub seed", "All lag/rolling use dates <= T-1"
        elif col in {"visitors", "target_source", "target_quality", "target_conflict", "target_missing"}:
            category, source, rule = "target", "Jiuzhaigou official/GitHub seed", "Target/quality metadata"
        elif col in {"sold_out_flag", "known_reserved_count", "daily_capacity", "booking_pressure_ratio", "official_notice_count"} or col.startswith("is_closed"):
            category, source, rule = "official_notice", "Jiuzhaigou official notices", "available_at <= T-1 23:59 for forecast-safe"
        elif "hsr" in col or "expressway" in col:
            category, source, rule = "transport_event", "National Railway Administration/Abazhou Government", "Public opening date"
        elif col in {"date", "year", "month", "day", "weekday", "day_of_year", "week_of_year", "quarter"} or "holiday" in col or col.startswith("is_week") or col.startswith("sin_") or col.startswith("cos_") or col.startswith("is_peak") or col.startswith("is_offseason") or col.startswith("is_summer") or col.startswith("is_winter") or col.startswith("is_month") or col == "is_rest_day" or col == "is_makeup_workday":
            category, source, rule = "calendar", "State Council calendar via chinese-calendar", "Known before target date"
        else:
            category, source, rule = "quality_or_metadata", "Pipeline", "Derived during build"
        rows.append(
            {
                "feature_name": col,
                "category": category,
                "dtype": str(explanatory[col].dtype),
                "source": source,
                "description": col.replace("_", " "),
                "forecast_safe": col in safe_cols,
                "available_at_rule": rule,
            }
        )
    for col in [c for c in safe.columns if c not in explanatory.columns]:
        rows.append(
            {
                "feature_name": col,
                "category": "attention_lag" if col.startswith("wiki_") else "forecast_safe_only",
                "dtype": str(safe[col].dtype),
                "source": "Wikimedia Pageviews API" if col.startswith("wiki_") else "Pipeline",
                "description": col.replace("_", " "),
                "forecast_safe": True,
                "available_at_rule": "Uses data available by T-1",
            }
        )
    dictionary = pd.DataFrame(rows).drop_duplicates("feature_name")
    dictionary.to_csv(root / "data/gold/feature_dictionary.csv", index=False, encoding="utf-8-sig")
    return dictionary
