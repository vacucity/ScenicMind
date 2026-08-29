from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path
from typing import Any

from .. import settings as _settings  # noqa: F401
from ..settings import MODEL_DIR
import numpy as np
import pandas as pd

from .dataset import data_availability


SEMANTIC_GROUPS = {
    "history": ("历史客流走势", "近期变化、周期规律与客流波动"),
    "calendar": ("节假日与季节", "节假日、休息日及季节性变化"),
    "weather": ("天气条件", "温度、降水、风力与恶劣天气"),
    "attention": ("网络关注度", "搜索热度与百科关注趋势"),
    "operation": ("预约与运营", "预约量、承载限制与官方公告"),
    "transport": ("交通可达性", "高铁、高速等交通条件变化"),
}


def _semantic_group_for(feature: str) -> str | None:
    if feature.startswith("visitors_"):
        return "history"
    if feature.startswith("weather_"):
        return "weather"
    if feature.startswith(("wiki_", "wechat_", "search_")):
        return "attention"
    if feature.startswith(("capacity", "daily_capacity", "known_reserved", "reservation", "sold_out", "official_notice")):
        return "operation"
    if "hsr" in feature or "expressway" in feature or feature.startswith("transport_"):
        return "transport"
    if feature.startswith("holiday_") or feature in {
        "year", "month", "weekday", "day_of_year", "week_of_year", "quarter",
        "sin_doy", "cos_doy", "sin_weekday", "cos_weekday", "is_weekend",
        "is_rest_day", "is_official_holiday", "is_summer_vacation",
        "is_winter_vacation", "is_peak_season", "is_offseason",
        "days_to_next_holiday",
    }:
        return "calendar"
    return None


def semantic_importance(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate technical model inputs into labels a dashboard audience can interpret."""
    totals = {key: 0.0 for key in SEMANTIC_GROUPS}
    for item in items:
        key = _semantic_group_for(str(item.get("feature", "")))
        if key:
            totals[key] += max(0.0, float(item.get("importance", 0.0)))
    total = sum(totals.values()) or 1.0
    groups = []
    for key, value in sorted(totals.items(), key=lambda pair: pair[1], reverse=True):
        if value <= 0:
            continue
        label, description = SEMANTIC_GROUPS[key]
        groups.append({
            "key": key,
            "label": label,
            "description": description,
            "importance": round(value / total * 100, 1),
        })
    return groups


def _lag(history: list[float], days: int, default: float) -> float:
    return float(history[-days]) if len(history) >= days else default


def _window(history: list[float], days: int) -> np.ndarray:
    values = history[-min(days, len(history)):]
    return np.asarray(values or [0.0], dtype=float)


@lru_cache(maxsize=1)
def load_flowstack():
    from scenicmind.flowstack.model import FlowStackModel

    if not (MODEL_DIR / "model.joblib").exists():
        raise FileNotFoundError(f"FlowStack 模型不存在：{MODEL_DIR}")
    return FlowStackModel.load(MODEL_DIR)


def _calendar_features(date: pd.Timestamp) -> dict[str, float | str]:
    day_of_year = date.dayofyear
    weekday = date.weekday()
    month_day = (date.month, date.day)
    return {
        "date": date,
        "holiday_name": "非节假日",
        "year": date.year,
        "month": date.month,
        "day": date.day,
        "weekday": weekday,
        "day_of_year": day_of_year,
        "week_of_year": int(date.isocalendar().week),
        "quarter": date.quarter,
        "is_weekend": int(weekday >= 5),
        "is_rest_day": int(weekday >= 5),
        "is_month_start": int(date.is_month_start),
        "is_month_end": int(date.is_month_end),
        "is_summer_vacation": int(date.month in (7, 8)),
        "is_winter_vacation": int(date.month in (1, 2)),
        "is_peak_season": int((4, 1) <= month_day <= (11, 15)),
        "is_offseason": int(not ((4, 1) <= month_day <= (11, 15))),
        "sin_doy": math.sin(2 * math.pi * day_of_year / 365.25),
        "cos_doy": math.cos(2 * math.pi * day_of_year / 365.25),
        "sin_weekday": math.sin(2 * math.pi * weekday / 7),
        "cos_weekday": math.cos(2 * math.pi * weekday / 7),
        "is_official_holiday": 0,
        "holiday_day_index": 0,
        "holiday_length": 0,
        "days_to_next_holiday": 30,
    }


def _flowstack_row(date: pd.Timestamp, history: list[float], source: pd.DataFrame, model) -> pd.DataFrame:
    default = float(np.median(history[-28:]))
    # feature_names_raw includes already one-hot encoded category columns. Feeding those
    # columns back together with holiday_name would make pandas create duplicate labels.
    # The inference frame must instead mirror the pre-encoding training frame.
    row: dict[str, Any] = dict(model.fill_values_)
    row.update(_calendar_features(date))
    recent = source.iloc[-1]
    for column in source.columns:
        if column not in {"date", "visitors"} and column in row:
            value = pd.to_numeric(pd.Series([recent[column]]), errors="coerce").iloc[0]
            if pd.notna(value):
                row[column] = float(value)

    for days in (1, 2, 3, 7, 14, 28, 365):
        row[f"visitors_lag_{days}"] = _lag(history, days, default)
    for days in (3, 7, 14, 28):
        values = _window(history, days)
        row[f"visitors_roll_mean_{days}"] = float(values.mean())
    for days in (7, 14):
        values = _window(history, days)
        row[f"visitors_roll_std_{days}"] = float(values.std())
    values7 = _window(history, 7)
    values14 = _window(history, 14)
    row.update({
        "visitors_roll_median_7": float(np.median(values7)),
        "visitors_roll_min_7": float(values7.min()),
        "visitors_roll_max_7": float(values7.max()),
        "visitors_roll_q25_14": float(np.quantile(values14, .25)),
        "visitors_roll_q75_14": float(np.quantile(values14, .75)),
        "visitors_trend_strength": float(values7[-1] - values7[0]) / max(len(values7) - 1, 1),
        "visitors_lag1_vs_ma7": _lag(history, 1, default) / max(float(values7.mean()), 1.0),
        "visitors_lag7_vs_ma28": _lag(history, 7, default) / max(float(_window(history, 28).mean()), 1.0),
    })
    return pd.DataFrame([row])


def _fallback_one(history: list[float], date: pd.Timestamp) -> float:
    default = float(np.mean(history[-7:]))
    weekday_values = [value for index, value in enumerate(history) if (len(history) - 1 - index) % 7 == 6]
    weekday_mean = float(np.mean(weekday_values[-4:])) if weekday_values else _lag(history, 7, default)
    recent_mean = float(np.mean(history[-7:]))
    trend = (float(np.mean(history[-7:])) - float(np.mean(history[-14:-7] or history[-7:]))) * 0.15
    weekend_factor = 1.08 if date.weekday() >= 5 else 1.0
    return max(0.0, (0.55 * weekday_mean + 0.3 * _lag(history, 14, default) + 0.15 * recent_mean + trend) * weekend_factor)


def _predict_one(history: list[float], date: pd.Timestamp, source: pd.DataFrame, model) -> float:
    if model is None:
        return _fallback_one(history, date)
    row = _flowstack_row(date, history, source, model)
    return float(model.predict(row).iloc[0]["predicted_visitors"])


def _metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float | int | None]:
    if not len(actual):
        return {"validationDays": 0, "mae": None, "rmse": None, "mape": None}
    error = actual - predicted
    nonzero = actual > 0
    return {
        "validationDays": int(len(actual)),
        "mae": round(float(np.mean(np.abs(error))), 2),
        "rmse": round(float(np.sqrt(np.mean(error ** 2))), 2),
        "mape": round(float(np.mean(np.abs(error[nonzero] / actual[nonzero])) * 100), 2) if nonzero.any() else None,
    }


def analyze_visitors(data: pd.DataFrame, file_name: str, warnings: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        model = load_flowstack()
        engine = "FlowStack"
        model_version = model.metadata.get("model_version", "flowstack")
    except Exception as error:  # pragma: no cover - exercised when artifact/runtime is unavailable
        model = None
        engine = "SeasonalLagFallback"
        model_version = "fallback-v1"
        warnings = [*warnings, f"FlowStack 加载失败，已使用季节滞后模型：{error}"]

    values = data["visitors"].astype(float).tolist()
    dates = pd.to_datetime(data["date"])
    validation_days = min(30, max(7, len(data) // 5))
    validation_start = max(14, len(data) - validation_days)
    backtest: dict[str, float] = {}
    for index in range(validation_start, len(data)):
        date = dates.iloc[index]
        prediction = _predict_one(values[:index], date, data.iloc[:index], model)
        backtest[date.strftime("%Y-%m-%d")] = prediction

    history = values.copy()
    future_points: list[dict[str, Any]] = []
    last_date = dates.iloc[-1]
    for offset in range(1, 31):
        date = last_date + pd.Timedelta(days=offset)
        prediction = _predict_one(history, date, data, model)
        prediction = float(max(0, round(prediction)))
        history.append(prediction)
        future_points.append({
            "date": date.strftime("%Y-%m-%d"),
            "actualVisitors": None,
            "predictedVisitors": int(prediction),
            "kind": "forecast",
        })

    history_points = []
    for _, row in data.tail(60).iterrows():
        date_text = pd.Timestamp(row["date"]).strftime("%Y-%m-%d")
        history_points.append({
            "date": date_text,
            "actualVisitors": int(round(float(row["visitors"]))),
            "predictedVisitors": int(round(backtest[date_text])) if date_text in backtest else None,
            "kind": "actual",
        })

    actual_validation = np.asarray([
        float(data.loc[index, "visitors"]) for index in range(validation_start, len(data))
    ])
    predicted_validation = np.asarray([
        backtest[dates.iloc[index].strftime("%Y-%m-%d")] for index in range(validation_start, len(data))
    ])
    metrics = _metrics(actual_validation, predicted_validation)
    latest_actual = int(round(values[-1]))
    latest_date = last_date.strftime("%Y-%m-%d")
    latest_prediction = backtest.get(latest_date)

    horizon_summary: dict[str, dict[str, int]] = {}
    for horizon in (7, 14, 30):
        predictions = [point["predictedVisitors"] for point in future_points[:horizon]]
        horizon_summary[str(horizon)] = {
            "average": int(round(float(np.mean(predictions)))),
            "peak": int(max(predictions)),
            "minimum": int(min(predictions)),
        }

    availability = data_availability(data)
    result = {
        "source": {
            "fileName": file_name,
            "rowCount": int(len(data)),
            "startDate": dates.iloc[0].strftime("%Y-%m-%d"),
            "endDate": latest_date,
            "warnings": warnings,
        },
        "model": {"name": engine, "version": model_version},
        "latestActual": {
            "date": latest_date,
            "visitors": latest_actual,
            "predictedVisitors": int(round(latest_prediction)) if latest_prediction is not None else None,
        },
        "historyPoints": history_points,
        "forecastPoints": future_points,
        "horizons": horizon_summary,
        "metrics": metrics,
        "dataAvailability": availability,
    }

    if model is not None:
        try:
            importance = model.importance_payload(top_k=None)
        except Exception as error:  # importance is intentionally off the dashboard hot path
            importance = {"model_version": model_version, "error": str(error), "feature_importance": []}
    else:
        importance = {
            "model_version": model_version,
            "degraded": True,
            "degraded_reason": "FlowStack 模型加载失败，已降级为季节滞后模型，特征重要性仅反映历史客流滞后项",
            "feature_importance": [
                {"feature": "visitors_lag_7", "group": "历史客流", "importance": .55, "rank": 1},
                {"feature": "visitors_lag_14", "group": "历史客流", "importance": .30, "rank": 2},
                {"feature": "visitors_roll_mean_7", "group": "历史客流", "importance": .15, "rank": 3},
            ],
        }
    importance["semantic_groups"] = semantic_importance(importance.get("feature_importance", []))
    return result, importance
