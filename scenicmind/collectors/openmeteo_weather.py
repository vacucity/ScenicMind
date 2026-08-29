from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd

from scenicmind.io import cached_get, write_parquet_and_csv

DAILY_VARS = [
    "temperature_2m_mean",
    "temperature_2m_max",
    "temperature_2m_min",
    "apparent_temperature_mean",
    "apparent_temperature_max",
    "precipitation_sum",
    "rain_sum",
    "snowfall_sum",
    "precipitation_hours",
    "weather_code",
    "wind_speed_10m_max",
    "wind_gusts_10m_max",
    "sunshine_duration",
]
HOURLY_VARS = ["relative_humidity_2m", "dew_point_2m", "cloud_cover", "surface_pressure", "wind_speed_10m"]


def _year_chunks(start: pd.Timestamp, end: pd.Timestamp):
    for year in range(start.year, end.year + 1):
        yield max(start, pd.Timestamp(year=year, month=1, day=1)), min(end, pd.Timestamp(year=year, month=12, day=31))


def collect(
    endpoint: str,
    root: Path,
    latitude: float,
    longitude: float,
    timezone: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    refresh: bool = False,
) -> pd.DataFrame:
    pieces: list[pd.DataFrame] = []
    for chunk_start, chunk_end in _year_chunks(start, end):
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": chunk_start.date().isoformat(),
            "end_date": chunk_end.date().isoformat(),
            "daily": ",".join(DAILY_VARS),
            "hourly": ",".join(HOURLY_VARS),
            "timezone": timezone,
            "wind_speed_unit": "kmh",
        }
        url = endpoint + "?" + urlencode(params)
        payload = cached_get(url, root / f"data/bronze/weather/{chunk_start.year}.json", refresh=refresh, pause_seconds=0.2)
        obj = json.loads(payload)
        daily = pd.DataFrame(obj["daily"]).rename(
            columns={
                "time": "date",
                "temperature_2m_mean": "actual_temp_mean",
                "temperature_2m_max": "actual_temp_max",
                "temperature_2m_min": "actual_temp_min",
                "apparent_temperature_mean": "actual_apparent_temp_mean",
                "apparent_temperature_max": "actual_apparent_temp_max",
                "precipitation_sum": "actual_precipitation_sum",
                "rain_sum": "actual_rain_sum",
                "snowfall_sum": "actual_snowfall_sum",
                "precipitation_hours": "actual_precipitation_hours",
                "weather_code": "actual_weather_code",
                "wind_speed_10m_max": "actual_wind_speed_max",
                "wind_gusts_10m_max": "actual_wind_gust_max",
                "sunshine_duration": "actual_sunshine_duration",
            }
        )
        daily["date"] = pd.to_datetime(daily["date"])
        hourly = pd.DataFrame(obj["hourly"])
        hourly["time"] = pd.to_datetime(hourly["time"])
        hourly["date"] = hourly["time"].dt.normalize()
        agg = hourly.groupby("date", as_index=False).agg(
            actual_humidity_mean=("relative_humidity_2m", "mean"),
            actual_humidity_max=("relative_humidity_2m", "max"),
            actual_dew_point_mean=("dew_point_2m", "mean"),
            actual_cloud_cover_mean=("cloud_cover", "mean"),
            actual_cloud_cover_max=("cloud_cover", "max"),
            actual_pressure_mean=("surface_pressure", "mean"),
            actual_wind_speed_mean=("wind_speed_10m", "mean"),
        )
        pieces.append(daily.merge(agg, on="date", how="left"))
    out = pd.concat(pieces, ignore_index=True).sort_values("date").drop_duplicates("date")
    write_parquet_and_csv(out, root / "data/silver/weather_daily.parquet")
    return out

