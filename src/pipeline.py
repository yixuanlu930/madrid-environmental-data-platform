from __future__ import annotations
import argparse
import traceback
from datetime import date, timedelta, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
from src.config import settings
from src.sources import fetch_historical_weather, fetch_air_quality
from src.storage import upload_pipeline_outputs
from src.transform import payload_to_hourly_wide_rows, wide_rows_to_long_rows, build_analytics_hourly_table, build_daily_summary
from src.utils import write_csv, write_json, read_json, read_csv

WEATHER_WIDE_FIELDS = ["source", "dataset", "date", "time", "latitude", "longitude", "temperature_2m", "temperature_2m_unit", "precipitation", "precipitation_unit"]
AIR_WIDE_FIELDS = ["source", "dataset", "date", "time", "latitude", "longitude", "ozone", "ozone_unit", "carbon_dioxide", "carbon_dioxide_unit"]
LONG_FIELDS = ["source", "dataset", "date", "time", "latitude", "longitude", "variable", "value", "unit"]
ANALYTICS_FIELDS = ["date", "time", "latitude", "longitude", "temperature_2m", "precipitation", "ozone", "carbon_dioxide"]
SUMMARY_FIELDS = ["date", "source", "dataset", "variable", "unit", "observations", "min_value", "avg_value", "max_value"]


def madrid_yesterday() -> date:
    return datetime.now(ZoneInfo(settings.timezone)).date() - timedelta(days=1)


def parse_date(value: str | None) -> date:
    if not value:
        return madrid_yesterday()
    return date.fromisoformat(value)


def _base_manifest(stage: str, day_string: str) -> dict[str, Any]:
    return {
        "stage": stage,
        "status": "running",
        "date": day_string,
        "coordinates": {
            "latitude": settings.latitude,
            "longitude": settings.longitude,
            "timezone": settings.timezone,
        },
        "outputs": [],
        "uploaded_to_minio": [],
        "row_counts": {},
        "errors": [],
    }


# ─────────────────────────────────────────────
#  STAGE 1 — INGESTA
#  Llama a las APIs y guarda los JSON en raw/
# ─────────────────────────────────────────────

def run_ingest(target_day: date | None = None) -> dict[str, Any]:
    day = target_day or madrid_yesterday()
    day_string = day.isoformat()
    data_dir = Path(settings.data_dir)
    manifest = _base_manifest("ingest", day_string)
    manifest["sources"] = []
    manifest["selected_variables"] = {
        "historical_weather": settings.weather_hourly_variables,
        "air_quality": settings.air_quality_hourly_variables,
    }

    try:
        weather_payload = fetch_historical_weather(day)
        raw_weather_path = data_dir / "raw" / "open_meteo_historical_weather" / f"date={day_string}" / "weather.json"
        write_json(raw_weather_path, weather_payload)
        manifest["sources"].append("open_meteo_historical_weather_api")
        manifest["outputs"].append(str(raw_weather_path))

        air_payload = fetch_air_quality(day)
        raw_air_path = data_dir / "raw" / "open_meteo_air_quality" / f"date={day_string}" / "air_quality.json"
        write_json(raw_air_path, air_payload)
        manifest["sources"].append("open_meteo_air_quality_api")
        manifest["outputs"].append(str(raw_air_path))

        manifest["uploaded_to_minio"] = upload_pipeline_outputs(data_dir / "raw", day_string)
        manifest["status"] = "success"

    except Exception as exc:
        manifest["status"] = "error"
        manifest["errors"].append({
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        })

    manifest_path = data_dir / "processed" / "manifests" / f"date={day_string}" / "manifest_ingest.json"
    write_json(manifest_path, manifest)
    manifest["manifest_path"] = str(manifest_path)
    return manifest


# ─────────────────────────────────────────────
#  STAGE 2 — PREPROCESAMIENTO
#  raw/ → clean/ + processed/
# ─────────────────────────────────────────────

def run_preprocess(target_day: date | None = None) -> dict[str, Any]:
    day = target_day or madrid_yesterday()
    day_string = day.isoformat()
    data_dir = Path(settings.data_dir)
    manifest = _base_manifest("preprocess", day_string)

    try:
        raw_weather_path = data_dir / "raw" / "open_meteo_historical_weather" / f"date={day_string}" / "weather.json"
        raw_air_path = data_dir / "raw" / "open_meteo_air_quality" / f"date={day_string}" / "air_quality.json"

        if not raw_weather_path.exists():
            raise FileNotFoundError(f"Raw weather file not found: {raw_weather_path}. Run ingest first.")
        if not raw_air_path.exists():
            raise FileNotFoundError(f"Raw air quality file not found: {raw_air_path}. Run ingest first.")

        weather_payload = read_json(raw_weather_path)
        air_payload = read_json(raw_air_path)

        weather_rows = payload_to_hourly_wide_rows(weather_payload, day, source="open_meteo", dataset="historical_weather", variables=settings.weather_hourly_variables)
        clean_weather_path = data_dir / "clean" / "historical_weather_hourly" / f"date={day_string}" / "weather_hourly.csv"
        write_csv(clean_weather_path, weather_rows, WEATHER_WIDE_FIELDS)
        manifest["outputs"].append(str(clean_weather_path))

        air_rows = payload_to_hourly_wide_rows(air_payload, day, source="open_meteo", dataset="air_quality", variables=settings.air_quality_hourly_variables)
        clean_air_path = data_dir / "clean" / "air_quality_hourly" / f"date={day_string}" / "air_quality_hourly.csv"
        write_csv(clean_air_path, air_rows, AIR_WIDE_FIELDS)
        manifest["outputs"].append(str(clean_air_path))

        long_rows = (
            wide_rows_to_long_rows(weather_rows, settings.weather_hourly_variables)
            + wide_rows_to_long_rows(air_rows, settings.air_quality_hourly_variables)
        )
        processed_path = data_dir / "processed" / "environment_observations_long" / f"date={day_string}" / "environment_observations_long.csv"
        write_csv(processed_path, long_rows, LONG_FIELDS)
        manifest["outputs"].append(str(processed_path))

        manifest["uploaded_to_minio"] = upload_pipeline_outputs(data_dir / "clean", day_string) + upload_pipeline_outputs(data_dir / "processed", day_string)
        manifest["row_counts"] = {
            "clean_historical_weather_hourly": len(weather_rows),
            "clean_air_quality_hourly": len(air_rows),
            "processed_long_observations": len(long_rows),
        }
        manifest["status"] = "success"

    except Exception as exc:
        manifest["status"] = "error"
        manifest["errors"].append({
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        })

    manifest_path = data_dir / "processed" / "manifests" / f"date={day_string}" / "manifest_preprocess.json"
    write_json(manifest_path, manifest)
    manifest["manifest_path"] = str(manifest_path)
    return manifest


# ─────────────────────────────────────────────
#  STAGE 3 — ANALÍTICA
#  processed/ → curated/
# ─────────────────────────────────────────────

def run_analytics(target_day: date | None = None) -> dict[str, Any]:
    day = target_day or madrid_yesterday()
    day_string = day.isoformat()
    data_dir = Path(settings.data_dir)
    manifest = _base_manifest("analytics", day_string)

    try:
        raw_weather_path = data_dir / "raw" / "open_meteo_historical_weather" / f"date={day_string}" / "weather.json"
        raw_air_path = data_dir / "raw" / "open_meteo_air_quality" / f"date={day_string}" / "air_quality.json"

        if not raw_weather_path.exists():
            raise FileNotFoundError(f"Raw weather file not found: {raw_weather_path}. Run ingest first.")
        if not raw_air_path.exists():
            raise FileNotFoundError(f"Raw air quality file not found: {raw_air_path}. Run ingest first.")

        weather_payload = read_json(raw_weather_path)
        air_payload = read_json(raw_air_path)

        weather_rows = payload_to_hourly_wide_rows(weather_payload, day, source="open_meteo", dataset="historical_weather", variables=settings.weather_hourly_variables)
        air_rows = payload_to_hourly_wide_rows(air_payload, day, source="open_meteo", dataset="air_quality", variables=settings.air_quality_hourly_variables)
        long_rows = (
            wide_rows_to_long_rows(weather_rows, settings.weather_hourly_variables)
            + wide_rows_to_long_rows(air_rows, settings.air_quality_hourly_variables)
        )

        analytics_rows = build_analytics_hourly_table(weather_rows, air_rows, day)
        curated_hourly_path = data_dir / "curated" / "hourly_environment_wide" / f"date={day_string}" / "hourly_environment_wide.csv"
        write_csv(curated_hourly_path, analytics_rows, ANALYTICS_FIELDS)
        manifest["outputs"].append(str(curated_hourly_path))

        summary_rows = build_daily_summary(long_rows, day)
        curated_summary_path = data_dir / "curated" / "daily_variable_summary" / f"date={day_string}" / "daily_variable_summary.csv"
        write_csv(curated_summary_path, summary_rows, SUMMARY_FIELDS)
        manifest["outputs"].append(str(curated_summary_path))

        manifest["uploaded_to_minio"] = upload_pipeline_outputs(data_dir / "curated", day_string)
        manifest["row_counts"] = {
            "curated_hourly_wide": len(analytics_rows),
            "curated_daily_summary": len(summary_rows),
        }
        manifest["status"] = "success"

    except Exception as exc:
        manifest["status"] = "error"
        manifest["errors"].append({
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        })

    manifest_path = data_dir / "processed" / "manifests" / f"date={day_string}" / "manifest_analytics.json"
    write_json(manifest_path, manifest)
    manifest["manifest_path"] = str(manifest_path)
    return manifest


# ─────────────────────────────────────────────
#  Compatibilidad — mantiene /run funcionando
# ─────────────────────────────────────────────

def run_pipeline(target_day: date | None = None) -> dict[str, Any]:
    ingest = run_ingest(target_day)
    if ingest["status"] != "success":
        return ingest
    preprocess = run_preprocess(target_day)
    if preprocess["status"] != "success":
        return preprocess
    return run_analytics(target_day)


def main() -> int:
    parser = argparse.ArgumentParser(description="Madrid Open-Meteo environmental pipeline")
    parser.add_argument("--date", default=None, help="Date in YYYY-MM-DD format. Defaults to yesterday in Europe/Madrid.")
    parser.add_argument("--stage", default="all", choices=["all", "ingest", "preprocess", "analytics"], help="Pipeline stage to run.")
    args = parser.parse_args()
    day = parse_date(args.date)
    if args.stage == "ingest":
        manifest = run_ingest(day)
    elif args.stage == "preprocess":
        manifest = run_preprocess(day)
    elif args.stage == "analytics":
        manifest = run_analytics(day)
    else:
        manifest = run_pipeline(day)
    print(manifest)
    return 0 if manifest.get("status") == "success" else 1

if __name__ == "__main__":
    raise SystemExit(main())
