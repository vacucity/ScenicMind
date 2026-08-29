from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from chinese_calendar import get_holiday_detail


NOTICE_VALUE_COLS = [
    "known_reserved_count",
    "daily_capacity",
    "sold_out_notice_lead_days",
    "booking_pressure_ratio",
]
HOLIDAY_VALUE_COLS = ["holiday_day_index", "holiday_length", "days_until_holiday_end"]
HISTORY_PREFIXES = ("visitors_lag_", "visitors_roll_")
HISTORY_SPECIAL = {"visitors_trend_strength", "visitors_lag1_vs_ma7", "visitors_lag7_vs_ma28"}


def _calendar_distances(dates: pd.Series) -> tuple[pd.Series, pd.Series]:
    start = pd.Timestamp(dates.min()) - pd.Timedelta(days=370)
    end = pd.Timestamp(dates.max()) + pd.Timedelta(days=370)
    extended = pd.date_range(start, end, freq="D")
    official = []
    for date in extended:
        try:
            is_holiday, name = get_holiday_detail(date.date())
        except NotImplementedError:
            continue
        if is_holiday and name:
            official.append(date)
    values = np.array(official, dtype="datetime64[ns]")
    to_next, since_prev = [], []
    for date in pd.to_datetime(dates):
        pos = np.searchsorted(values, date.to_datetime64(), side="left")
        to_next.append(int((pd.Timestamp(values[pos]) - date).days))
        prev_pos = np.searchsorted(values, date.to_datetime64(), side="right") - 1
        since_prev.append(int((date - pd.Timestamp(values[prev_pos])).days))
    return pd.Series(to_next, index=dates.index), pd.Series(since_prev, index=dates.index)


def _clean_history(frame: pd.DataFrame, imputed: dict[str, int]) -> pd.DataFrame:
    out = frame.copy()
    visitors = pd.to_numeric(out["visitors"], errors="coerce")
    past_median = visitors.shift(1).expanding(min_periods=1).median()
    past_std = visitors.shift(1).expanding(min_periods=2).std().fillna(0)
    week_reference = pd.to_numeric(out.get("visitors_lag_7"), errors="coerce")
    fallback_level = week_reference.combine_first(past_median)
    history_cols = [c for c in out if c.startswith(HISTORY_PREFIXES)]
    out["historical_target_imputed_count"] = out[history_cols].isna().sum(axis=1).astype("int16")
    for col in history_cols:
        missing = int(out[col].isna().sum())
        if not missing:
            continue
        series = pd.to_numeric(out[col], errors="coerce")
        if "std_" in col:
            series = series.fillna(past_std)
        else:
            series = series.fillna(fallback_level)
        out[col] = series
        imputed[col] = missing

    # Recompute ratios after their component features have been made complete.
    if {"visitors_roll_mean_7", "visitors_roll_mean_28"}.issubset(out.columns):
        denom = out["visitors_roll_mean_28"].replace(0, np.nan)
        out["visitors_trend_strength"] = (out["visitors_roll_mean_7"] / denom).fillna(1.0)
    if {"visitors_lag_1", "visitors_roll_mean_7"}.issubset(out.columns):
        denom = out["visitors_roll_mean_7"].replace(0, np.nan)
        out["visitors_lag1_vs_ma7"] = (out["visitors_lag_1"] / denom).fillna(1.0)
    if {"visitors_lag_7", "visitors_roll_mean_28"}.issubset(out.columns):
        denom = out["visitors_roll_mean_28"].replace(0, np.nan)
        out["visitors_lag7_vs_ma28"] = (out["visitors_lag_7"] / denom).fillna(1.0)
    return out


def clean_frame(frame: pd.DataFrame, *, forecast_safe: bool) -> tuple[pd.DataFrame, dict]:
    out = frame.copy()
    out["date"] = pd.to_datetime(out["date"], errors="raise")
    out = out.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)
    for col in out.select_dtypes(include=["object", "string"]):
        out[col] = out[col].astype("string").str.strip().replace("", pd.NA)

    missing_before = int(out.isna().sum().sum())
    rows_before = len(out)
    target_missing_rows = int(out["visitors"].isna().sum())
    imputed: dict[str, int] = {}

    # Keep the full spine while creating strictly past-only historical fallbacks.
    out = _clean_history(out, imputed)

    # No notice means no known reservation/capacity signal, not an unknown value.
    for col in NOTICE_VALUE_COLS:
        if col in out:
            missing_mask = out[col].isna()
            out[f"{col}_known"] = (~missing_mask).astype("int8")
            imputed[col] = int(missing_mask.sum())
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)

    out["holiday_name"] = out["holiday_name"].fillna("非节假日")
    imputed["holiday_name"] = int(frame["holiday_name"].isna().sum())
    for col in HOLIDAY_VALUE_COLS:
        if col in out:
            imputed[col] = int(out[col].isna().sum())
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)
    out["days_to_next_holiday"], out["days_since_prev_holiday"] = _calendar_distances(out["date"])

    wiki_cols = [c for c in out if c.startswith("wiki_")]
    for col in wiki_cols:
        missing_mask = out[col].isna()
        if not missing_mask.any():
            continue
        out[f"{col}_was_missing"] = missing_mask.astype("int8")
        numeric = pd.to_numeric(out[col], errors="coerce")
        if forecast_safe:
            # Forward fill only; leading warm-up rows remain missing and are dropped below.
            out[col] = numeric.ffill()
        else:
            out[col] = numeric.interpolate(method="linear", limit_direction="both")
        imputed[col] = int(missing_mask.sum())

    # Rows without a label cannot train supervised models. Do not fabricate visitors.
    out = out[out["visitors"].notna()].copy()
    out["visitors"] = pd.to_numeric(out["visitors"], errors="raise").round().astype("int64")
    out["target_source"] = out["target_source"].fillna("unknown")
    out["target_quality"] = out["target_quality"].fillna("unknown")
    if "target_conflict" in out:
        out["target_conflict"] = out["target_conflict"].fillna(0).astype("int8")

    # Remove only leading warm-up rows that cannot be filled without future information.
    remaining_missing_cols = out.columns[out.isna().any()].tolist()
    warmup_mask = out[remaining_missing_cols].isna().any(axis=1) if remaining_missing_cols else pd.Series(False, index=out.index)
    warmup_rows = int(warmup_mask.sum())
    out = out.loc[~warmup_mask].copy()

    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    out = out.reset_index(drop=True)
    report = {
        "forecast_safe": forecast_safe,
        "rows_before": rows_before,
        "rows_after": len(out),
        "target_missing_rows_dropped": target_missing_rows,
        "warmup_or_unfillable_rows_dropped": warmup_rows,
        "missing_cells_before": missing_before,
        "missing_cells_after": int(out.isna().sum().sum()),
        "duplicate_dates_after": int(out["date"].duplicated().sum()),
        "negative_visitors_after": int((pd.to_numeric(out["visitors"]) < 0).sum()),
        "imputed_cells_by_column": imputed,
    }
    return out, report


def clean_files(root: Path) -> dict:
    inputs = {
        "explanatory": root / "jiuzhaigou_daily_explanatory.csv",
        "forecast_safe_h1": root / "jiuzhaigou_daily_forecast_safe_h1.csv",
    }
    outputs = {
        "explanatory": root / "jiuzhaigou_daily_explanatory_clean.csv",
        "forecast_safe_h1": root / "jiuzhaigou_daily_forecast_safe_h1_clean.csv",
    }
    reports = {}
    for name, input_path in inputs.items():
        frame = pd.read_csv(input_path)
        cleaned, report = clean_frame(frame, forecast_safe=name == "forecast_safe_h1")
        if cleaned.isna().any().any():
            raise AssertionError(f"{name} still contains missing cells")
        cleaned.to_csv(outputs[name], index=False, encoding="utf-8-sig")
        reports[name] = report
    report_path = root / "reports/cleaning_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
    return reports


if __name__ == "__main__":
    print(json.dumps(clean_files(Path.cwd()), ensure_ascii=False, indent=2))
