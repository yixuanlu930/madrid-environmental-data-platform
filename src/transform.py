
from __future__ import annotations
from collections import defaultdict
from datetime import date
from statistics import mean
from typing import Any
from src.config import settings
from src.utils import safe_float

WEATHER_UNITS = {"temperature_2m": "°C", "precipitation": "mm"}
AIR_QUALITY_UNITS = {"ozone": "μg/m³", "carbon_dioxide": "ppm"}


def payload_to_hourly_wide_rows(payload: dict[str, Any], day: date, source: str, dataset: str, variables: list[str]) -> list[dict[str, Any]]:
    hourly = payload.get("hourly", {})
    units = payload.get("hourly_units", {}) or {}
    times = hourly.get("time", [])
    rows: list[dict[str, Any]] = []
    for i, timestamp in enumerate(times):
        row = {
            "source": source,
            "dataset": dataset,
            "date": day.isoformat(),
            "time": timestamp,
            "latitude": payload.get("latitude", settings.latitude),
            "longitude": payload.get("longitude", settings.longitude),
        }
        for variable in variables:
            values = hourly.get(variable, [])
            row[variable] = values[i] if i < len(values) else ""
            row[f"{variable}_unit"] = units.get(variable, WEATHER_UNITS.get(variable, AIR_QUALITY_UNITS.get(variable, "")))
        rows.append(row)
    return rows


def wide_rows_to_long_rows(rows: list[dict[str, Any]], variables: list[str]) -> list[dict[str, Any]]:
    long_rows: list[dict[str, Any]] = []
    for row in rows:
        for variable in variables:
            long_rows.append({
                "source": row.get("source", ""),
                "dataset": row.get("dataset", ""),
                "date": row.get("date", ""),
                "time": row.get("time", ""),
                "latitude": row.get("latitude", ""),
                "longitude": row.get("longitude", ""),
                "variable": variable,
                "value": row.get(variable, ""),
                "unit": row.get(f"{variable}_unit", ""),
            })
    return long_rows


def build_analytics_hourly_table(weather_rows: list[dict[str, Any]], air_rows: list[dict[str, Any]], day: date) -> list[dict[str, Any]]:
    by_time: dict[str, dict[str, Any]] = {}
    for row in weather_rows + air_rows:
        timestamp = row["time"]
        if timestamp not in by_time:
            by_time[timestamp] = {"date": day.isoformat(), "time": timestamp, "latitude": settings.latitude, "longitude": settings.longitude}
        for key, value in row.items():
            if key in {"source", "dataset", "date", "time", "latitude", "longitude"} or key.endswith("_unit"):
                continue
            by_time[timestamp][key] = value
    return [by_time[t] for t in sorted(by_time)]


def build_daily_summary(long_rows: list[dict[str, Any]], day: date) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str], list[float]] = defaultdict(list)
    for row in long_rows:
        value = safe_float(row.get("value"))
        if value is None:
            continue
        key = (str(row.get("source", "")), str(row.get("dataset", "")), str(row.get("variable", "")), str(row.get("unit", "")))
        groups[key].append(value)
    summary = []
    for (source, dataset, variable, unit), values in sorted(groups.items()):
        summary.append({
            "date": day.isoformat(),
            "source": source,
            "dataset": dataset,
            "variable": variable,
            "unit": unit,
            "observations": len(values),
            "min_value": round(min(values), 4),
            "avg_value": round(mean(values), 4),
            "max_value": round(max(values), 4),
        })
    return summary
