import argparse
import csv
from datetime import date, timedelta
from pathlib import Path

REQUIRED_RELATIVE_PATHS = [
    "raw/open_meteo/historical_weather/date={date}/weather.json",
    "raw/datos_madrid/air_quality_accumulated/date={date}/air_quality_accumulated.csv",
    "clean/open_meteo/historical_weather/date={date}/weather_hourly_clean.csv",
    "clean/datos_madrid/air_quality_accumulated/date={date}/air_quality_hourly_clean.csv",
    "processed/environment_observations/date={date}/environment_observations.csv",
    "curated/daily_environment_summary/date={date}/daily_environment_summary.csv",
    "processed/manifests/date={date}/manifest.json",
]


def default_date():
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

    print(f"Validating outputs for date={args.date}")
    for template in REQUIRED_RELATIVE_PATHS:
        path = data_dir / template.format(date=args.date)
        if not path.exists() or path.stat().st_size == 0:
            print(f"[ERROR] Missing or empty: {path}")
            ok = False
        else:
            detail = ""
            if path.suffix == ".csv":
                detail = f" rows={count_csv_rows(path)}"
            print(f"[OK] {path}{detail}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
