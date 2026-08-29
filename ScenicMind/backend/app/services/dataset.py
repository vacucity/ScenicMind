from __future__ import annotations

import json
from pathlib import Path

from .. import settings as _settings  # noqa: F401 - initializes local scientific dependencies
import numpy as np
import pandas as pd


DATE_ALIASES = ("date", "日期", "day", "ds", "时间", "统计日期")
VISITOR_ALIASES = (
    "visitors", "客流量", "游客量", "游客人数", "入园人数", "visitor_count",
    "actual_visitors", "y",
)


class DatasetError(ValueError):
    pass


def _read_csv(path: Path) -> pd.DataFrame:
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError as error:
            last_error = error
    raise DatasetError("CSV 编码无法识别，请使用 UTF-8 或 GB18030") from last_error


def read_uploaded_dataset(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    try:
        if suffix == ".csv":
            return _read_csv(path)
        if suffix in {".xlsx", ".xls"}:
            return pd.read_excel(path, sheet_name=0)
        if suffix == ".json":
            try:
                return pd.read_json(path)
            except ValueError:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    payload = payload.get("data", payload.get("rows", payload))
                return pd.DataFrame(payload)
        if suffix == ".parquet":
            return pd.read_parquet(path)
    except (OSError, ValueError, ImportError) as error:
        raise DatasetError(f"文件读取失败：{error}") from error
    raise DatasetError("仅支持 CSV、XLSX、XLS、JSON 和 Parquet 文件")


def _find_column(columns: list[str], aliases: tuple[str, ...]) -> str | None:
    normalized = {str(column).strip().lower(): column for column in columns}
    for alias in aliases:
        if alias.lower() in normalized:
            return normalized[alias.lower()]
    return None


def normalize_dataset(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    if frame.empty:
        raise DatasetError("上传文件没有数据")
    data = frame.copy()
    data.columns = [str(column).strip() for column in data.columns]
    date_column = _find_column(list(data.columns), DATE_ALIASES)
    visitor_column = _find_column(list(data.columns), VISITOR_ALIASES)
    if date_column is None or visitor_column is None:
        raise DatasetError("数据必须包含日期列 date/日期 和真实客流列 visitors/客流量")

    raw_dates = data[date_column]
    if pd.api.types.is_numeric_dtype(raw_dates):
        numeric = pd.to_numeric(raw_dates, errors="coerce")
        if numeric.dropna().median() > 20_000:
            dates = pd.Timestamp("1899-12-30") + pd.to_timedelta(numeric, unit="D")
        else:
            dates = pd.to_datetime(raw_dates, errors="coerce")
    else:
        dates = pd.to_datetime(raw_dates, errors="coerce")
    visitors = pd.to_numeric(
        data[visitor_column].astype(str).str.replace(",", "", regex=False), errors="coerce"
    )
    data["date"] = dates.dt.normalize()
    data["visitors"] = visitors
    data = data.dropna(subset=["date", "visitors"])
    data = data[np.isfinite(data["visitors"]) & (data["visitors"] >= 0)]
    if data.empty:
        raise DatasetError("日期或真实客流列没有可用值")

    warnings: list[str] = []
    duplicate_count = int(data.duplicated("date").sum())
    if duplicate_count:
        warnings.append(f"发现 {duplicate_count} 条重复日期，已按日期保留最后一条")
        data = data.sort_values("date").drop_duplicates("date", keep="last")
    data = data.sort_values("date").reset_index(drop=True)
    if len(data) < 21:
        raise DatasetError("至少需要 21 天的连续日客流数据才能进行预测")
    gaps = data["date"].diff().dt.days.dropna()
    missing_days = int((gaps - 1).clip(lower=0).sum())
    if missing_days:
        warnings.append(f"日期序列缺少约 {missing_days} 天，滞后特征将使用最近可用数据")
    if len(data) < 60:
        warnings.append("数据少于 60 天，预测稳定性可能有限")
    return data, warnings


def data_availability(data: pd.DataFrame) -> dict[str, dict[str, object]]:
    columns = {column.lower() for column in data.columns}

    def availability(label: str, prefixes: tuple[str, ...]) -> dict[str, object]:
        matched = sorted(column for column in data.columns if column.lower().startswith(prefixes))
        return {
            "label": label,
            "status": "uploaded" if matched else "requires_source",
            "source": "上传数据" if matched else None,
            "columns": matched,
        }

    result = {
        "actualVisitors": {"label": "真实客流", "status": "uploaded", "source": "上传数据", "columns": ["visitors"]},
        "weather": availability("天气特征", ("weather_", "actual_temp", "temperature", "天气", "气温")),
        "reservation": availability("预约数据", ("reservation", "reserved", "known_reserved", "booking", "预约")),
        "capacity": availability("景区承载量", ("daily_capacity", "capacity", "承载量")),
        "notice": availability("景区公告", ("official_notice", "notice", "公告")),
        "attention": availability("网络关注度", ("wiki_", "wechat_", "search_", "搜索")),
    }
    return result
