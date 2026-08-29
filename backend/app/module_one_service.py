"""模块一（客流预测）服务实现。

接入 master 分支的 FlowStack 模型，对九寨沟日客流做真实回测 + 未来 7 天预测。
数据来自 backend/data/jiuzhaigou_daily.csv，模型来自 artifacts/flowstack/current/model。
契约（ModuleOneData）保持不变，`demo` 标记为 False 表示已接入真实模型。
"""

from __future__ import annotations

from datetime import date

from .flowstack_forecast import CAPACITY, load_data, run_forecast
from .module_one_contracts import (
    ForecastDay,
    HistoryPoint,
    ModuleOneData,
    TodaySnapshot,
    WeekDay,
)

_CN_WEEKDAY = ("一", "二", "三", "四", "五", "六", "日")


def _level(value: int, capacity: int) -> str:
    rate = value / capacity
    if rate >= 0.75:
        return "较高"
    if rate >= 0.5:
        return "正常"
    return "较低"


def _p90(value: int, capacity: int) -> int:
    """点预测近似 P90 上界：FlowStack 输出点预测，此处按 +10% 保守上浮并封顶承载量。"""
    return min(capacity, round(value * 1.10))


def build_forecast(spot_id: str, spot_name: str, capacity: int = CAPACITY) -> ModuleOneData:
    data = load_data()
    result = run_forecast(data, horizon=7)

    # 返回全部历史数据（2019-09 起，约 1869 天），前端按 7D/30D/全部 切换可见窗口。
    history = [
        HistoryPoint(date=date.fromisoformat(item["date"]), visitors=int(item["actualVisitors"]))
        for item in result["historyPoints"][:-1]
    ]

    forecast = [
        ForecastDay(
            date=date.fromisoformat(item["date"]),
            predicted=int(item["predictedVisitors"]),
            p90=_p90(int(item["predictedVisitors"]), capacity),
            level=_level(int(item["predictedVisitors"]), capacity),
        )
        for item in result["forecastPoints"]
    ]

    latest_date = date.fromisoformat(result["latestActual"]["date"])
    latest_visitors = int(result["latestActual"]["visitors"])

    # 最近一个已观测日作为"今天"，未来 7 天从次日起；周同比取 7 天前同点对比。
    values = data["visitors"].astype(float).tolist()
    prev_week = values[-8] if len(values) >= 8 else values[0]
    wow = (latest_visitors - prev_week) / prev_week * 100 if prev_week else 0.0
    today = TodaySnapshot(
        date=latest_date,
        predicted=latest_visitors,
        range_low=round(latest_visitors * 0.90),
        range_high=min(capacity, round(latest_visitors * 1.10)),
        level=_level(latest_visitors, capacity),
        entered=latest_visitors,
        entered_time=f"数据更新至 {latest_date:%Y-%m-%d}",
        entered_wow=f"较上周同期 {'+' if wow >= 0 else ''}{wow:.1f}%",
    )

    week = [
        WeekDay(day=_CN_WEEKDAY[item.date.weekday()], value=item.predicted, level=item.level)
        for item in forecast
    ]

    return ModuleOneData(
        spot_id=spot_id,
        spot_name=spot_name,
        capacity=capacity,
        today=today,
        history=history,
        forecast=forecast,
        week=week,
        demo=False,
    )