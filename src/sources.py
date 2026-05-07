import csv
import io
import requests
from datetime import date
from typing import Any

from src.config import settings


def fetch_open_meteo_weather(day: date) -> dict[str, Any]:
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": settings.latitude,
        "longitude": settings.longitude,
        "start_date": day.isoformat(),
        "end_date": day.isoformat(),
        "hourly": ",".join([
            "temperature_2m",
            "relative_humidity_2m",
            "precipitation",
            "wind_speed_10m",
            "shortwave_radiation",
        ]),
        "timezone": settings.timezone,
    }
    response = requests.get(url, params=params, timeout=60)
    response.raise_for_status()
    return response.json()


def fetch_datos_madrid_air_quality_csv() -> str:
    response = requests.get(settings.madrid_air_csv_url, timeout=60)
    response.raise_for_status()
    # Some CSV files from public portals are served with Windows encodings.
    if not response.encoding or response.encoding.lower() == "iso-8859-1":
        response.encoding = "latin-1"
    return response.text


def read_semicolon_csv(text: str) -> list[dict[str, str]]:
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ";"
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    return [dict(row) for row in reader]
