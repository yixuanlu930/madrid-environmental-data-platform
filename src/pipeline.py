from __future__ import annotations

import argparse
import traceback
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from src.config import settings
from src.sources import fetch_open_meteo_weather, fetch_datos_madrid_air_quality_csv, read_semicolon_csv
from src.transform import open_meteo_to_clean_rows, madrid_air_to_clean_rows, build_daily_summary
from src.utils import write_json, write_text, write_csv
from src.storage import upload_pipeline_outputs


OBSERVATION_FIELDS = [
    "source",
    "dataset",
    "date",
    "time",
    "latitude",
    "longitude",
    "station_id",
    "metric",
    "metric_name",
    "value",
    "unit",
    "quality_flag",
]

SUMMARY_FIELDS = [
    "date",
    "source",
    "dataset",
    "metric_name",
    "observations",
    "min_value",
    "avg_value",
    "max_value",
]


def default_execution_date() -> date:
    return date.today() - timedelta(days=1)


def parse_date(value: str | None) -> date:
    if not value:
        return default_execution_date()
    return date.fromisoformat(value)


def run_pipeline(target_day: date | None = None) -> dict[str, Any]:
    day = target_day or default_execution_date()
    day_string = day.isoformat()
    data_dir = Path(settings.data_dir)

    manifest: dict[str, Any] = {
        "status": "running",
        "date": day_string,
        "sources": [],
        "outputs": [],
        "uploaded_to_minio": [],
        "errors": [],
    }

    try:
        # 1) RAW zone: exact source responses, without loss.
        weather_payload = fetch_open_meteo_weather(day)
        raw_weather_path = data_dir / "raw" / "open_meteo" / "historical_weather" / f"date={day_string}" / "weather.json"
        write_json(raw_weather_path, weather_payload)
        manifest["sources"].append("open_meteo_historical_weather")
        manifest["outputs"].append(str(raw_weather_path))

        madrid_csv_text = fetch_datos_madrid_air_quality_csv()
        raw_madrid_path = data_dir / "raw" / "datos_madrid" / "air_quality_accumulated" / f"date={day_string}" / "air_quality_accumulated.csv"
        write_text(raw_madrid_path, madrid_csv_text)
        manifest["sources"].append("datos_madrid_air_quality_accumulated")
        manifest["outputs"].append(str(raw_madrid_path))

        # 2) CLEAN zone: homogeneous tabular format per source.
        clean_weather_rows = open_meteo_to_clean_rows(weather_payload, day)
        clean_weather_path = data_dir / "clean" / "open_meteo" / "historical_weather" / f"date={day_string}" / "weather_hourly_clean.csv"
        write_csv(clean_weather_path, clean_weather_rows, OBSERVATION_FIELDS)
        manifest["outputs"].append(str(clean_weather_path))

        raw_madrid_rows = read_semicolon_csv(madrid_csv_text)
        clean_madrid_rows = madrid_air_to_clean_rows(raw_madrid_rows, day)
        clean_madrid_path = data_dir / "clean" / "datos_madrid" / "air_quality_accumulated" / f"date={day_string}" / "air_quality_hourly_clean.csv"
        write_csv(clean_madrid_path, clean_madrid_rows, OBSERVATION_FIELDS)
        manifest["outputs"].append(str(clean_madrid_path))

        # 3) PROCESSED zone: unified analytical dataset.
        processed_rows = clean_weather_rows + clean_madrid_rows
        processed_path = data_dir / "processed" / "environment_observations" / f"date={day_string}" / "environment_observations.csv"
        write_csv(processed_path, processed_rows, OBSERVATION_FIELDS)
        manifest["outputs"].append(str(processed_path))

        # 4) CURATED zone: daily summaries ready for notebooks/BI.
        curated_rows = build_daily_summary(processed_rows, day)
        curated_path = data_dir / "curated" / "daily_environment_summary" / f"date={day_string}" / "daily_environment_summary.csv"
        write_csv(curated_path, curated_rows, SUMMARY_FIELDS)
        manifest["outputs"].append(str(curated_path))

        # 5) Upload all generated outputs to object storage.
        uploaded = upload_pipeline_outputs(data_dir, day_string)
        manifest["uploaded_to_minio"] = uploaded

        manifest["status"] = "success"
        manifest["row_counts"] = {
            "weather_clean": len(clean_weather_rows),
            "madrid_air_quality_clean": len(clean_madrid_rows),
            "processed_observations": len(processed_rows),
            "curated_summary": len(curated_rows),
        }

    except Exception as exc:
        manifest["status"] = "error"
        manifest["errors"].append({
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        })

    manifest_path = data_dir / "processed" / "manifests" / f"date={day_string}" / "manifest.json"
    write_json(manifest_path, manifest)
    manifest["manifest_path"] = str(manifest_path)

    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Madrid environmental data pipeline")
    parser.add_argument("--date", default=None, help="Execution date in YYYY-MM-DD format. Defaults to yesterday.")
    args = parser.parse_args()

    target_day = parse_date(args.date)
    manifest = run_pipeline(target_day)
    print(manifest)

    return 0 if manifest.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
