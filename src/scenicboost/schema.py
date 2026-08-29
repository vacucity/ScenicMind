from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd


TARGET_COLUMN = "visitors"
DATE_COLUMN = "date"

# These fields describe labels, collection quality or cleaning rather than the
# state known at forecast time. They must never enter the estimator.
EXCLUDED_FEATURES = {
    DATE_COLUMN,
    TARGET_COLUMN,
    "target_source",
    "target_quality",
    "target_conflict",
    "target_missing",
    "feature_missing_count",
    "quality_score",
    "historical_target_imputed_count",
}

FORBIDDEN_EXACT = {
    "visitors_github",
    "visitors_official",
    "visitors_diff_1",
    "visitors_diff_7",
    "visitors_wow",
}


def feature_group(feature: str) -> str:
    if feature.startswith(("visitors_lag_", "visitors_roll_")) or feature in {
        "visitors_trend_strength",
        "visitors_lag1_vs_ma7",
        "visitors_lag7_vs_ma28",
    }:
        return "历史客流"
    if feature.startswith("wiki_"):
        return "网络关注度"
    if "hsr" in feature or "expressway" in feature:
        return "交通可达性"
    if feature in {
        "official_notice_count",
        "sold_out_flag",
        "is_closed",
        "is_reopen",
        "is_partial_open",
        "discount_flag",
        "free_ticket_flag",
        "capacity_restricted",
        "sold_out_notice_lead_days",
        "known_reserved_count",
        "daily_capacity",
        "booking_pressure_ratio",
        "known_reserved_count_known",
        "daily_capacity_known",
        "sold_out_notice_lead_days_known",
        "booking_pressure_ratio_known",
    }:
        return "景区运营"
    calendar_tokens = (
        "holiday",
        "week",
        "month",
        "quarter",
        "vacation",
        "season",
        "day_of_year",
        "weekday",
        "sin_",
        "cos_",
        "is_rest_day",
        "is_makeup_workday",
    )
    if feature in {"year", "day"} or any(token in feature for token in calendar_tokens):
        return "日历节假日"
    return "其他"


def validate_forecast_safe_columns(columns: Iterable[str]) -> None:
    columns = set(columns)
    failures: list[str] = []
    actual = sorted(c for c in columns if c.startswith("actual_"))
    if actual:
        failures.append(f"包含当天实况字段: {actual}")
    forbidden = sorted(columns & FORBIDDEN_EXACT)
    if forbidden:
        failures.append(f"包含禁止的目标变换字段: {forbidden}")
    if failures:
        raise ValueError("T+1 特征安全检查失败；" + "；".join(failures))


def validate_training_frame(
    frame: pd.DataFrame,
    *,
    date_column: str = DATE_COLUMN,
    target_column: str = TARGET_COLUMN,
) -> pd.DataFrame:
    missing = [c for c in (date_column, target_column) if c not in frame]
    if missing:
        raise ValueError(f"训练数据缺少必需字段: {missing}")
    validate_forecast_safe_columns(frame.columns)
    out = frame.copy()
    out[date_column] = pd.to_datetime(out[date_column], errors="raise")
    out = out.sort_values(date_column).reset_index(drop=True)
    if out[date_column].duplicated().any():
        duplicated = out.loc[out[date_column].duplicated(False), date_column].dt.strftime("%Y-%m-%d").tolist()
        raise ValueError(f"日粒度数据存在重复日期: {duplicated[:10]}")
    out[target_column] = pd.to_numeric(out[target_column], errors="raise")
    if out[target_column].isna().any():
        raise ValueError("目标客流存在空值")
    if (out[target_column] < 0).any():
        raise ValueError("目标客流存在负数")
    return out


def select_model_features(
    frame: pd.DataFrame,
    *,
    date_column: str = DATE_COLUMN,
    target_column: str = TARGET_COLUMN,
) -> tuple[list[str], list[str]]:
    validate_forecast_safe_columns(frame.columns)
    excluded = EXCLUDED_FEATURES | {date_column, target_column}
    features = [c for c in frame.columns if c not in excluded]
    features = [c for c in features if not c.startswith("actual_")]
    categorical = [
        c
        for c in features
        if pd.api.types.is_object_dtype(frame[c].dtype)
        or isinstance(frame[c].dtype, pd.StringDtype)
        or isinstance(frame[c].dtype, pd.CategoricalDtype)
    ]
    if not features:
        raise ValueError("没有可用于训练的预测特征")
    return features, categorical


def prepare_features(
    frame: pd.DataFrame,
    feature_names: list[str],
    categorical_features: list[str],
) -> pd.DataFrame:
    missing = [c for c in feature_names if c not in frame]
    if missing:
        raise ValueError(f"预测输入缺少模型字段: {missing}")
    out = frame.loc[:, feature_names].copy()
    categorical = set(categorical_features)
    for col in feature_names:
        if col in categorical:
            out[col] = out[col].astype("string").fillna("__MISSING__").astype(str)
        else:
            out[col] = pd.to_numeric(out[col], errors="coerce")
            out[col] = out[col].replace([np.inf, -np.inf], np.nan)
    return out


def scene_keys(row: pd.Series) -> list[str]:
    keys: list[str] = []
    holiday_name = str(row.get("holiday_name", "非节假日"))
    holiday_flag = int(float(row.get("is_official_holiday", 0) or 0))
    holiday_day = int(float(row.get("holiday_day_index", 0) or 0))
    if holiday_flag or holiday_name not in {"非节假日", "None", "nan", ""}:
        if holiday_day > 0:
            keys.append(f"holiday:{holiday_name}:day:{holiday_day}")
        keys.extend([f"holiday:{holiday_name}", "holiday:any"])
    if int(float(row.get("is_summer_vacation", 0) or 0)):
        keys.append("season:summer_vacation")
    if int(float(row.get("is_peak_season", 0) or 0)):
        keys.append("season:peak")
    if int(float(row.get("is_offseason", 0) or 0)):
        keys.append("season:offseason")
    if int(float(row.get("is_weekend", 0) or 0)):
        keys.append("calendar:weekend")
    else:
        keys.append("calendar:weekday")
    keys.append("global")
    return keys

