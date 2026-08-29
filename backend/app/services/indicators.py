"""指标蓝图计算引擎 —— 从上传数据动态计算 8 大模块指标。

计算逻辑全部基于 DataFrame 列，不依赖特定文件名。
新数据上传后 analyze_visitors 完成即自动调用，无需额外配置。
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd


def _safe_div(numerator: float, denominator: float) -> float | None:
    if denominator == 0 or pd.isna(denominator) or pd.isna(numerator):
        return None
    return round(float(numerator) / float(denominator), 4)


def _col(df: pd.DataFrame, *names: str) -> str | None:
    """从 DataFrame 中按优先级查找列名。"""
    lower_map = {c.lower(): c for c in df.columns}
    for name in names:
        if name.lower() in lower_map:
            return lower_map[name.lower()]
    return None


def _latest(df: pd.DataFrame, col: str | None) -> Any:
    if col is None or col not in df.columns:
        return None
    series = df[col].dropna()
    return series.iloc[-1] if len(series) else None


def _recent(df: pd.DataFrame, col: str | None, days: int) -> list:
    if col is None or col not in df.columns:
        return []
    return df[col].dropna().tail(days).tolist()


def _percentile(values: list[float], pct: float) -> float:
    clean = [v for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))]
    if not clean:
        return 0
    return float(np.percentile(clean, pct))


def compute_indicators(data: pd.DataFrame) -> dict[str, Any]:
    """主入口：接收标准化后的 DataFrame，输出 8 大模块指标。"""
    if data.empty:
        return {"error": "数据为空"}

    visitors_col = _col(data, "visitors", "客流量", "游客量")
    date_col = _col(data, "date", "日期")
    capacity_col = _col(data, "daily_capacity", "capacity", "承载量")
    sold_out_col = _col(data, "sold_out_flag", "售罄标记")
    restricted_col = _col(data, "capacity_restricted", "限流标记")
    reserved_col = _col(data, "known_reserved_count", "known_reserved", "预订量")
    notice_col = _col(data, "official_notice_count", "notice_count", "公告数")

    is_holiday_col = _col(data, "is_official_holiday", "is_holiday")
    is_rest_col = _col(data, "is_rest_day", "is_rest")
    is_peak_col = _col(data, "is_peak_season", "peak_season")
    is_summer_col = _col(data, "is_summer_vacation", "summer_vacation")
    is_winter_col = _col(data, "is_winter_vacation", "winter_vacation")
    holiday_name_col = _col(data, "holiday_name", "节假日名称")
    holiday_idx_col = _col(data, "holiday_day_index", "holiday_index")
    holiday_len_col = _col(data, "holiday_length", "holiday_len")

    hsr_col = _col(data, "huanglong_jiuzhai_hsr_open", "hsr_open", "huanglong_jiuzhai_hsr_open")
    hsr_days_col = _col(data, "days_since_hsr_open", "hsr_days")
    expressway_col = _col(data, "jiuzhai_mianyang_expressway_open", "expressway_open")
    expressway_days_col = _col(data, "days_since_expressway_open", "expressway_days")

    precip_col = _col(data, "weather_precip_lag1", "precip_lag1", "降水量")
    bad_weather_col = _col(data, "weather_bad_flag_lag1", "bad_flag_lag1")
    rain_col = _col(data, "weather_is_rain_lag1", "is_rain_lag1")
    temp_col = _col(data, "weather_temp_mean_lag1", "temp_mean_lag1")
    snow_col = _col(data, "weather_snow_lag1", "snow_lag1")

    wiki_zh_col = _col(data, "wiki_zh_views_lag1", "wiki_zh_lag1")
    wiki_zh_ma_col = _col(data, "wiki_zh_views_ma7", "wiki_zh_ma7")
    wiki_en_col = _col(data, "wiki_en_views_lag1", "wiki_en_lag1")
    wiki_en_ma_col = _col(data, "wiki_en_views_ma7", "wiki_en_ma7")
    wechat_col = _col(data, "wechat_search_index_lag1", "wechat_lag1")

    lag1_col = _col(data, "visitors_lag_1", "lag_1")
    lag365_col = _col(data, "visitors_lag_365", "lag_365")
    lag7_col = _col(data, "visitors_lag_7", "lag_7")
    roll_mean7_col = _col(data, "visitors_roll_mean_7", "roll_mean_7")
    roll_std7_col = _col(data, "visitors_roll_std_7", "roll_std_7")
    roll_max7_col = _col(data, "visitors_roll_max_7", "roll_max_7")
    roll_min7_col = _col(data, "visitors_roll_min_7", "roll_min_7")
    trend_col = _col(data, "visitors_trend_strength", "trend_strength")
    lag1_vs_ma7_col = _col(data, "visitors_lag1_vs_ma7", "lag1_vs_ma7")

    result: dict[str, Any] = {}

    # ===================================================================
    # 模块1：客流规模与趋势
    # ===================================================================
    if visitors_col:
        visitors = data[visitors_col].astype(float)
        latest_v = float(visitors.iloc[-1])
        total = float(visitors.sum())
        avg = float(visitors.mean())
        p95 = _percentile(visitors.tolist(), 95)
        p50 = _percentile(visitors.tolist(), 50)

        yoy = None
        if lag365_col and lag365_col in data.columns:
            yoy_val = _latest(data, lag365_col)
            if yoy_val is not None and yoy_val > 0:
                yoy = round((latest_v - float(yoy_val)) / float(yoy_val) * 100, 1)

        mom = None
        if lag1_col and lag1_col in data.columns:
            lag1_val = _latest(data, lag1_col)
            if lag1_val is not None and lag1_val > 0:
                mom = round((latest_v - float(lag1_val)) / float(lag1_val) * 100, 1)

        roll_mean7 = _latest(data, roll_mean7_col) if roll_mean7_col else None
        roll_std7 = _latest(data, roll_std7_col) if roll_std7_col else None
        roll_max7 = _latest(data, roll_max7_col) if roll_max7_col else None
        roll_min7 = _latest(data, roll_min7_col) if roll_min7_col else None
        trend = _latest(data, trend_col) if trend_col else None

        recent_30 = _recent(data, visitors_col, 30)
        result["visitorTrend"] = {
            "latest": int(round(latest_v)),
            "total": int(round(total)),
            "average": int(round(avg)),
            "p95": int(round(p95)),
            "median": int(round(p50)),
            "yoyChange": yoy,
            "momChange": mom,
            "rollMean7": round(float(roll_mean7), 1) if roll_mean7 is not None else None,
            "rollStd7": round(float(roll_std7), 1) if roll_std7 is not None else None,
            "rollMax7": int(round(float(roll_max7))) if roll_max7 is not None else None,
            "rollMin7": int(round(float(roll_min7))) if roll_min7 is not None else None,
            "trendStrength": round(float(trend), 3) if trend is not None else None,
            "recent30": [int(round(v)) for v in recent_30],
        }

    # ===================================================================
    # 模块2：承载与售罄
    # ===================================================================
    capacity_metrics: dict[str, Any] = {}
    if visitors_col and capacity_col and capacity_col in data.columns:
        cap_series = data[capacity_col].astype(float)
        vis_series = data[visitors_col].astype(float)
        valid_mask = cap_series > 0
        if valid_mask.any():
            load_rates = (vis_series[valid_mask] / cap_series[valid_mask] * 100).clip(0, 200)
            latest_cap = float(cap_series.iloc[-1])
            latest_vis = float(vis_series.iloc[-1])
            latest_rate = round(latest_vis / latest_cap * 100, 1) if latest_cap > 0 else None
            capacity_metrics["latestLoadRate"] = latest_rate
            capacity_metrics["avgLoadRate"] = round(float(load_rates.mean()), 1)
            capacity_metrics["maxLoadRate"] = round(float(load_rates.max()), 1)
            capacity_metrics["overCapacityDays"] = int((load_rates > 100).sum())
            capacity_metrics["nearCapacityDays"] = int((load_rates >= 90).sum())

    if sold_out_col and sold_out_col in data.columns:
        sold = data[sold_out_col]
        capacity_metrics["soldOutDays"] = int(sold.sum())
        capacity_metrics["soldOutRate"] = round(float(sold.mean()) * 100, 1)
    if restricted_col and restricted_col in data.columns:
        capacity_metrics["restrictedDays"] = int(data[restricted_col].sum())
        capacity_metrics["restrictedRate"] = round(float(data[restricted_col].mean()) * 100, 1)
    if reserved_col and reserved_col in data.columns:
        capacity_metrics["latestReserved"] = int(_latest(data, reserved_col) or 0)
    if notice_col and notice_col in data.columns:
        capacity_metrics["noticeCount"] = int(_latest(data, notice_col) or 0)

    if capacity_metrics:
        result["capacity"] = capacity_metrics

    # ===================================================================
    # 模块3：节假日效应
    # ===================================================================
    holiday_metrics: dict[str, Any] = {}
    if visitors_col:
        vis = data[visitors_col].astype(float)
        if is_holiday_col and is_holiday_col in data.columns:
            holiday_mask = data[is_holiday_col].astype(bool)
            if holiday_mask.any():
                holiday_metrics["holidayAvg"] = int(round(float(vis[holiday_mask].mean())))
                holiday_metrics["holidayDays"] = int(holiday_mask.sum())
            else:
                holiday_metrics["holidayAvg"] = None
                holiday_metrics["holidayDays"] = 0
            non_holiday_mask = ~holiday_mask
            if non_holiday_mask.any():
                holiday_metrics["weekdayAvg"] = int(round(float(vis[non_holiday_mask].mean())))
            if holiday_metrics.get("holidayAvg") and holiday_metrics.get("weekdayAvg"):
                holiday_metrics["holidayLift"] = round(
                    (holiday_metrics["holidayAvg"] - holiday_metrics["weekdayAvg"])
                    / holiday_metrics["weekdayAvg"] * 100, 1
                )
        if is_peak_col and is_peak_col in data.columns:
            peak_mask = data[is_peak_col].astype(bool)
            if peak_mask.any():
                holiday_metrics["peakSeasonAvg"] = int(round(float(vis[peak_mask].mean())))
                holiday_metrics["peakSeasonDays"] = int(peak_mask.sum())
            off_peak = ~peak_mask
            if off_peak.any():
                holiday_metrics["offSeasonAvg"] = int(round(float(vis[off_peak].mean())))
        if is_summer_col and is_summer_col in data.columns:
            summer_mask = data[is_summer_col].astype(bool)
            if summer_mask.any():
                holiday_metrics["summerAvg"] = int(round(float(vis[summer_mask].mean())))
        if is_winter_col and is_winter_col in data.columns:
            winter_mask = data[is_winter_col].astype(bool)
            if winter_mask.any():
                holiday_metrics["winterAvg"] = int(round(float(vis[winter_mask].mean())))

        # 各假期逐日客流曲线
        if holiday_name_col and holiday_idx_col and holiday_name_col in data.columns and holiday_idx_col in data.columns:
            curves: dict[str, list] = {}
            for name in data[holiday_name_col].unique():
                if name == "非节假日" or name is None:
                    continue
                subset = data[(data[holiday_name_col] == name) & (data[holiday_idx_col] > 0)]
                if subset.empty:
                    continue
                by_day = subset.groupby(holiday_idx_col)[visitors_col].mean().sort_index()
                curves[str(name)] = [int(round(v)) for v in by_day.tolist()]
            if curves:
                holiday_metrics["holidayCurves"] = curves

    if holiday_metrics:
        result["holidayEffect"] = holiday_metrics

    # ===================================================================
    # 模块4：天气影响
    # ===================================================================
    weather_metrics: dict[str, Any] = {}
    if visitors_col:
        vis = data[visitors_col].astype(float)
        if precip_col and precip_col in data.columns:
            precip = pd.to_numeric(data[precip_col], errors="coerce").fillna(0)
            rainy = precip > 0
            if rainy.any():
                weather_metrics["rainyDays"] = int(rainy.sum())
                weather_metrics["rainyDayAvgVisitors"] = int(round(float(vis[rainy].mean())))
            dry = ~rainy
            if dry.any():
                weather_metrics["dryDayAvgVisitors"] = int(round(float(vis[dry].mean())))
            if weather_metrics.get("rainyDayAvgVisitors") and weather_metrics.get("dryDayAvgVisitors"):
                weather_metrics["rainImpactRate"] = round(
                    (weather_metrics["rainyDayAvgVisitors"] - weather_metrics["dryDayAvgVisitors"])
                    / weather_metrics["dryDayAvgVisitors"] * 100, 1
                )
            weather_metrics["maxPrecip"] = round(float(precip.max()), 1)
        if bad_weather_col and bad_weather_col in data.columns:
            bad = data[bad_weather_col].astype(bool)
            if bad.any():
                weather_metrics["badWeatherDays"] = int(bad.sum())
                weather_metrics["badWeatherAvgVisitors"] = int(round(float(vis[bad].mean())))
            weather_metrics["badWeatherImpactRate"] = round(
                (weather_metrics.get("badWeatherAvgVisitors", 0) - weather_metrics.get("dryDayAvgVisitors", 0))
                / max(weather_metrics.get("dryDayAvgVisitors", 1), 1) * 100, 1
            ) if weather_metrics.get("badWeatherAvgVisitors") and weather_metrics.get("dryDayAvgVisitors") else None
        if temp_col and temp_col in data.columns:
            temp = pd.to_numeric(data[temp_col], errors="coerce")
            weather_metrics["avgTemp"] = round(float(temp.mean()), 1)
            weather_metrics["minTemp"] = round(float(temp.min()), 1)
            weather_metrics["maxTemp"] = round(float(temp.max()), 1)

    if weather_metrics:
        result["weather"] = weather_metrics

    # ===================================================================
    # 模块5：交通基建
    # ===================================================================
    transport_metrics: dict[str, Any] = {}
    if hsr_col and hsr_col in data.columns and visitors_col:
        vis = data[visitors_col].astype(float)
        hsr_open = data[hsr_col].astype(bool)
        if hsr_open.any():
            transport_metrics["hsrOpenDays"] = int(hsr_open.sum())
            transport_metrics["hsrOpenAvgVisitors"] = int(round(float(vis[hsr_open].mean())))
        hsr_closed = ~hsr_open
        if hsr_closed.any():
            transport_metrics["hsrClosedAvgVisitors"] = int(round(float(vis[hsr_closed].mean())))
        if transport_metrics.get("hsrOpenAvgVisitors") and transport_metrics.get("hsrClosedAvgVisitors"):
            transport_metrics["hsrLiftRate"] = round(
                (transport_metrics["hsrOpenAvgVisitors"] - transport_metrics["hsrClosedAvgVisitors"])
                / transport_metrics["hsrClosedAvgVisitors"] * 100, 1
            )
    if expressway_col and expressway_col in data.columns and visitors_col:
        vis = data[visitors_col].astype(float)
        exp_open = data[expressway_col].astype(bool)
        if exp_open.any():
            transport_metrics["expOpenDays"] = int(exp_open.sum())
            transport_metrics["expOpenAvgVisitors"] = int(round(float(vis[exp_open].mean())))
        exp_closed = ~exp_open
        if exp_closed.any():
            transport_metrics["expClosedAvgVisitors"] = int(round(float(vis[exp_closed].mean())))
        if transport_metrics.get("expOpenAvgVisitors") and transport_metrics.get("expClosedAvgVisitors"):
            transport_metrics["expLiftRate"] = round(
                (transport_metrics["expOpenAvgVisitors"] - transport_metrics["expClosedAvgVisitors"])
                / transport_metrics["expClosedAvgVisitors"] * 100, 1
            )

    if transport_metrics:
        result["transport"] = transport_metrics

    # ===================================================================
    # 模块6：网络热度
    # ===================================================================
    attention_metrics: dict[str, Any] = {}
    if wiki_zh_col and wiki_zh_col in data.columns:
        attention_metrics["wikiZhLatest"] = int(_latest(data, wiki_zh_col) or 0)
        attention_metrics["wikiZhAvg"] = int(round(float(pd.to_numeric(data[wiki_zh_col], errors="coerce").mean())))
    if wiki_en_col and wiki_en_col in data.columns:
        attention_metrics["wikiEnLatest"] = int(_latest(data, wiki_en_col) or 0)
        attention_metrics["wikiEnAvg"] = int(round(float(pd.to_numeric(data[wiki_en_col], errors="coerce").mean())))
    if wechat_col and wechat_col in data.columns:
        attention_metrics["wechatLatest"] = int(_latest(data, wechat_col) or 0)
    # 热度与客流相关性
    if wiki_zh_col and wiki_zh_col in data.columns and visitors_col:
        try:
            corr = float(pd.to_numeric(data[wiki_zh_col], errors="coerce").corr(data[visitors_col].astype(float)))
            attention_metrics["correlationWithVisitors"] = round(corr, 3)
        except Exception:
            pass

    if attention_metrics:
        result["attention"] = attention_metrics

    # ===================================================================
    # 模块7：数据质量
    # ===================================================================
    quality_metrics: dict[str, Any] = {}
    quality_metrics["totalRows"] = int(len(data))
    quality_metrics["totalColumns"] = int(len(data.columns))
    if date_col and date_col in data.columns:
        dates = pd.to_datetime(data[date_col], errors="coerce")
        quality_metrics["dateStart"] = str(dates.min().date()) if not dates.isna().all() else None
        quality_metrics["dateEnd"] = str(dates.max().date()) if not dates.isna().all() else None
        # 检测缺失日期
        if not dates.isna().all():
            full_range = pd.date_range(dates.min(), dates.max(), freq="D")
            missing_dates = len(full_range) - len(dates.dropna().unique())
            quality_metrics["missingDates"] = int(max(0, missing_dates))
    # 封顶值检测
    if visitors_col and visitors_col in data.columns:
        capped = (data[visitors_col] >= 41000).sum()
        quality_metrics["cappedDays"] = int(capped)
    # 缺失值统计
    missing_counts = data.isnull().sum()
    cols_with_missing = {col: int(count) for col, count in missing_counts.items() if count > 0}
    quality_metrics["columnsWithMissing"] = cols_with_missing
    # 异常尖峰
    if lag1_vs_ma7_col and lag1_vs_ma7_col in data.columns:
        ratios = pd.to_numeric(data[lag1_vs_ma7_col], errors="coerce")
        outliers = (ratios > 3).sum()
        quality_metrics["spikeOutliers"] = int(outliers)

    result["dataQuality"] = quality_metrics

    return result
