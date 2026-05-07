
import argparse
import csv
import json
from datetime import date, timedelta
from pathlib import Path

REQUIRED_FILES = [
    "raw/open_meteo_historical_weather/date={date}/weather.json",
    "raw/open_meteo_air_quality/date={date}/air_quality.json",
    "clean/historical_weather_hourly/date={date}/weather_hourly.csv",
    "clean/air_quality_hourly/date={date}/air_quality_hourly.csv",
    "processed/environment_observations_long/date={date}/environment_observations_long.csv",
    "curated/hourly_environment_wide/date={date}/hourly_environment_wide.csv",
    "curated/daily_variable_summary/date={date}/daily_variable_summary.csv",
    "processed/manifests/date={date}/manifest.json",
]

def default_date() -> str:
    return (date.today() - timedelta(days=1)).isoformat()

def count_csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8") as f:
        return max(0, sum(1 for _ in csv.DictReader(f)))

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=default_date(), help="Date in YYYY-MM-DD format")
    parser.add_argument("--data-dir", default="/app/data")
    args = parser.parse_args()
    data_dir = Path(args.data_dir)
    ok = True
    print(f"Validating Madrid Open-Meteo outputs for date={args.date}")
    expected_csv_rows = {
        "clean/historical_weather_hourly/date={date}/weather_hourly.csv": 24,
        "clean/air_quality_hourly/date={date}/air_quality_hourly.csv": 24,
        "processed/environment_observations_long/date={date}/environment_observations_long.csv": 96,
        "curated/hourly_environment_wide/date={date}/hourly_environment_wide.csv": 24,
        "curated/daily_variable_summary/date={date}/daily_variable_summary.csv": 4,
    }
    for template in REQUIRED_FILES:
        path = data_dir / template.format(date=args.date)
        if not path.exists() or path.stat().st_size == 0:
            print(f"[ERROR] Missing or empty: {path}")
            ok = False
            continue
        detail = ""
        if path.suffix == ".csv":
            rows = count_csv_rows(path)
            expected = expected_csv_rows.get(template)
            detail = f" rows={rows}"
            if expected is not None and rows != expected:
                detail += f" expected={expected}"
                print(f"[ERROR] {path}{detail}")
                ok = False
                continue
        if path.name == "manifest.json":
            manifest = json.loads(path.read_text(encoding="utf-8"))
            if manifest.get("status") != "success":
                print(f"[ERROR] Manifest status is not success: {manifest.get('status')}")
                ok = False
                continue
        print(f"[OK] {path}{detail}")
    return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
