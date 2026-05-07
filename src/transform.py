from __future__ import annotations

from collections import defaultdict
from datetime import date
from statistics import mean
from typing import Any

from src.utils import normalize_name, safe_float


OPEN_METEO_UNITS_DEFAULTS = {
    "temperature_2m": "°C",
    "relative_humidity_2m": "%",
    "precipitation": "mm",
    "wind_speed_10m": "km/h",
    "shortwave_radiation": "W/m²",
}


MADRID_MAGNITUDES = {
    "1": "sulfur_dioxide",
    "6": "carbon_monoxide",
    "7": "nitrogen_monoxide",
    "8": "nitrogen_dioxide",
    "9": "particles_pm2_5",
    "10": "particles_pm10",
    "12": "nitrogen_oxides",
    "14": "ozone",
    "20": "toluene",
    "30": "benzene",
    "35": "ethylbenzene",
    "37": "metaxylene",
    "38": "paraxylene",
    "39": "orthoxylene",
    "42": "total_hydrocarbons",
    "43": "methane",
    "44": "non_methane_hydrocarbons",
}


def open_meteo_to_clean_rows(payload: dict[str, Any], day: date) -> list[dict[str, Any]]:
    hourly = payload.get("hourly", {})
    units = payload.get("hourly_units", {}) or {}
    times = hourly.get("time", [])
    rows: list[dict[str, Any]] = []

    for metric, values in hourly.items():
        if metric == "time":
            continue
        for i, value in enumerate(values):
            rows.append({
                "source": "open_meteo",
                "dataset": "historical_weather",
                "date": day.isoformat(),
                "time": times[i] if i < len(times) else "",
                "latitude": payload.get("latitude", ""),
                "longitude": payload.get("longitude", ""),
                "station_id": "",
                "metric": metric,
                "metric_name": metric,
                "value": value,
                "unit": units.get(metric, OPEN_METEO_UNITS_DEFAULTS.get(metric, "")),
                "quality_flag": "",
            })
    return rows


def madrid_air_to_clean_rows(raw_rows: list[dict[str, str]], day: date) -> list[dict[str, Any]]:
    clean: list[dict[str, Any]] = []
    target_year = day.year
    target_month = day.month
    target_day = day.day

    for row in raw_rows:
        norm = {normalize_name(k or ""): (v or "").strip() for k, v in row.items()}

        try:
            year = int(norm.get("ano") or norm.get("anio") or norm.get("year") or 0)
            month = int(norm.get("mes") or norm.get("month") or 0)
            day_num = int(norm.get("dia") or norm.get("day") or 0)
        except ValueError:
            continue

        if (year, month, day_num) != (target_year, target_month, target_day):
            continue

        station_id = norm.get("estacion", "")
        magnitude_code = str(norm.get("magnitud", "")).strip()
        metric_name = MADRID_MAGNITUDES.get(magnitude_code, f"magnitude_{magnitude_code}" if magnitude_code else "unknown")

        for hour in range(1, 25):
            h_col = f"h{hour:02d}"
            v_col = f"v{hour:02d}"
            value = safe_float(norm.get(h_col))
            if value is None:
                continue

            clean.append({
                "source": "datos_madrid",
                "dataset": "air_quality_accumulated",
                "date": day.isoformat(),
                "time": f"{day.isoformat()}T{hour - 1:02d}:00",
                "latitude": "",
                "longitude": "",
                "station_id": station_id,
                "metric": magnitude_code,
                "metric_name": metric_name,
                "value": value,
                "unit": "official_unit_by_magnitude",
                "quality_flag": norm.get(v_col, ""),
            })

    return clean


def build_daily_summary(rows: list[dict[str, Any]], day: date) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[float]] = defaultdict(list)

    for row in rows:
        value = safe_float(row.get("value"))
        if value is None:
            continue
        key = (str(row.get("source", "")), str(row.get("dataset", "")), str(row.get("metric_name", "")))
        groups[key].append(value)

    summary: list[dict[str, Any]] = []
    for (source, dataset, metric_name), values in sorted(groups.items()):
        summary.append({
            "date": day.isoformat(),
            "source": source,
            "dataset": dataset,
            "metric_name": metric_name,
            "observations": len(values),
            "min_value": round(min(values), 4),
            "avg_value": round(mean(values), 4),
            "max_value": round(max(values), 4),
        })
    return summary
