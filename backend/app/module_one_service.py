"""模块一（客流预测）服务实现。

当前为演示口径：在模块一接入真实预测模型（历史时序、天气、预约、搜索热度等
特征）之前，返回固定种子、可复现的演示数据，数字口径与模块二的 `_demo_forecast`
保持一致，保证看板与经营报告峰值对得上。

接入真实模型时，只需替换 `build_forecast` 的数据来源，契约定不变。
"""

import random
from datetime import date, timedelta

from .module_one_contracts import (
    ForecastDay,
    HistoryPoint,
    ModuleOneData,
    TodaySnapshot,
    WeekDay,
)

CAPACITY = 55_000

# 与 module_two._demo_forecast 保持一致，确保峰值/峰值日前后端统一。
FORECAST_VALUES = (26_500, 28_800, 31_500, 33_800, 42_100, 47_600, 35_900)

_CN_WEEKDAY = ("一", "二", "三", "四", "五", "六", "日")


def _level(value: int, capacity: int) -> str:
    rate = value / capacity
    if rate >= 0.75:
        return "较高"
    if rate >= 0.5:
        return "正常"
    return "较低"


def _history(days: int = 30) -> list[HistoryPoint]:
    """过去 `days` 天的入园量演示序列（固定种子，结果可复现）。"""
    rng = random.Random(20260828)
    base = 33_500
    points: list[HistoryPoint] = []
    for offset in range(days, 0, -1):
        day = date.today() - timedelta(days=offset)
        weekend_boost = 9_500 if day.weekday() >= 5 else 0
        noise = rng.randint(-3_800, 3_800)
        visitors = max(18_000, base + weekend_boost + noise)
        points.append(HistoryPoint(date=day, visitors=visitors))
    return points


def _forecast(capacity: int) -> list[ForecastDay]:
    """未来 7 天预测（明天起），数字与模块二演示预测对齐。"""
    start = date.today() + timedelta(days=1)
    result: list[ForecastDay] = []
    for index, value in enumerate(FORECAST_VALUES):
        day = start + timedelta(days=index)
        result.append(
            ForecastDay(
                date=day,
                predicted=value,
                p90=min(capacity, round(value * 1.14)),
                level=_level(value, capacity),
            )
        )
    return result


def _week(forecast: list[ForecastDay]) -> list[WeekDay]:
    return [
        WeekDay(day=_CN_WEEKDAY[item.date.weekday()], value=item.predicted, level=item.level)
        for item in forecast
    ]


def _today() -> TodaySnapshot:
    """今日预测快照。2026-08-29 为周六，旺季高峰日。"""
    return TodaySnapshot(
        date=date.today(),
        predicted=42_000,
        range_low=39_000,
        range_high=45_000,
        level="较高",
        entered=28_400,
        entered_time="截至 14:00",
        entered_wow="较上周同期 +8.4%",
    )


def build_forecast(spot_id: str, spot_name: str, capacity: int = CAPACITY) -> ModuleOneData:
    forecast = _forecast(capacity)
    return ModuleOneData(
        spot_id=spot_id,
        spot_name=spot_name,
        capacity=capacity,
        today=_today(),
        history=_history(),
        forecast=forecast,
        week=_week(forecast),
        demo=True,
    )