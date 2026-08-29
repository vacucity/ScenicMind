"""模块一（客流预测）统一契约。

与模块二共用 CamelModel，保证前后端字段命名一致（camelCase）。
"""

from datetime import date
from typing import Literal

from pydantic import Field

from .module_two_contracts import CamelModel


class TodaySnapshot(CamelModel):
    date: date
    predicted: int = Field(ge=0)
    range_low: int = Field(ge=0)
    range_high: int = Field(ge=0)
    level: Literal["较低", "正常", "较高"]
    entered: int = Field(ge=0)
    entered_time: str
    entered_wow: str


class HistoryPoint(CamelModel):
    date: date
    visitors: int = Field(ge=0)


class ForecastDay(CamelModel):
    date: date
    predicted: int = Field(ge=0)
    p90: int = Field(ge=0)
    level: Literal["较低", "正常", "较高"]


class WeekDay(CamelModel):
    day: str
    value: int = Field(ge=0)
    level: Literal["较低", "正常", "较高"]


class ModuleOneData(CamelModel):
    spot_id: str
    spot_name: str
    capacity: int = Field(gt=0)
    today: TodaySnapshot
    history: list[HistoryPoint]
    forecast: list[ForecastDay]
    week: list[WeekDay]
    demo: bool = True