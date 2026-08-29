"""模块一（客流预测）真实引擎：接入 FlowStack 模型做九寨沟日客流预测。

把 master 里的 `services/forecast.py` 核心推理逻辑移植进来，去掉上传/入库/鉴权等
外围，只保留与看板直接相关的部分：加载 FlowStack 模型 → 回测 → 未来 30 天预测
→ 指标与特征重要性。数据来自 backend/data/jiuzhaigou_daily.csv。
"""

from __future__ import annotations

import math
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# 仓库根目录（backend/app/flowstack_forecast.py -> parents[2]）
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MODEL_DIR = ROOT / "artifacts" / "flowstack" / "current" / "model"
DATA_PATH = ROOT / "backend" / "data" / "jiuzhaigou_daily.csv"

# 九寨沟官方日限流承载量约 4.1 万人，与历史峰值 41,000 一致。
CAPACITY = 41_000


@lru_cache(maxsize=1)
def load_flowstack():
    """惰性加载 FlowStack 模型（进程内只加载一次）。"""
    from src.flowstack.model import FlowStackModel

    model_path = MODEL_DIR / "model.joblib"
    if not model_path.exists():
        raise FileNotFoundError(f"FlowStack 模型不存在：{MODEL_DIR}")
    return FlowStackModel.load(MODEL_DIR)


def load_data() -> pd.DataFrame:
    """读取九寨沟日客流数据并按日期排序；缺失文件时回退到内置样本列。"""
    if DATA_PATH.exists():
        data = pd.read_csv(DATA_PATH)
    else:
        raise FileNotFoundError(f"九寨沟客流数据不存在：{DATA_PATH}")
    data.columns = [str(c).strip() for c in data.columns]
    data["date"] = pd.to_datetime(data["date"]).dt.normalize()
    data["visitors"] = pd.to_numeric(
        data["visitors"].astype(str).str.replace(",", "", regex=False), errors="coerce"
    )
    data = data.dropna(subset=["date", "visitors"])
    data = data[data["visitors"] >= 0]
    return data.sort_values("date").reset_index(drop=True)


def _lag(history: list[float], days: int, default: float) -> float:
    return float(history[-days]) if len(history) >= days else default


def _window(history: list[float], days: int) -> np.ndarray:
    values = history[-min(days, len(history)):]
    return np.asarray(values or [0.0], dtype=float)


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


def _flowstack_row(
    date: pd.Timestamp, history: list[float], source: pd.DataFrame, model
) -> pd.DataFrame:
    default = float(np.median(history[-28:]))
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


def _metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, Any]:
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


def run_forecast(data: pd.DataFrame, horizon: int = 30) -> dict[str, Any]:
    """对九寨沟数据做回测 + 未来 horizon 天预测，返回看板可消费的结构。"""
    last_error: Exception | None = None
    try:
        model = load_flowstack()
        engine = "FlowStack"
        model_version = model.metadata.get("model_version", "flowstack")
    except Exception as error:  # 模型/依赖不可用时降级为季节滞后模型
        model = None
        engine = "SeasonalLagFallback"
        model_version = "fallback-v1"
        last_error = error

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
    for offset in range(1, horizon + 1):
        date = last_date + pd.Timedelta(days=offset)
        prediction = _predict_one(history, date, data, model)
        prediction = float(max(0, round(prediction)))
        history.append(prediction)
        future_points.append({
            "date": date.strftime("%Y-%m-%d"),
            "predictedVisitors": int(prediction),
            "kind": "forecast",
        })

    history_points: list[dict[str, Any]] = []
    for _, row in data.iterrows():
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

    return {
        "model": {"name": engine, "version": model_version, "error": str(last_error) if last_error else None},
        "latestActual": {"date": latest_date, "visitors": latest_actual},
        "historyPoints": history_points,
        "forecastPoints": future_points,
        "metrics": metrics,
    }