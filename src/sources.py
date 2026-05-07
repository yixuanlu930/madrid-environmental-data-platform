
from datetime import date
from typing import Any
import requests
from src.config import settings


def fetch_historical_weather(day: date) -> dict[str, Any]:
    params = {
        "latitude": settings.latitude,
        "longitude": settings.longitude,
        "start_date": day.isoformat(),
        "end_date": day.isoformat(),
        "hourly": ",".join(settings.weather_hourly_variables),
        "timezone": settings.timezone,
    }
    response = requests.get(settings.historical_weather_url, params=params, timeout=60)
    response.raise_for_status()
    return response.json()


def fetch_air_quality(day: date) -> dict[str, Any]:
    params = {
        "latitude": settings.latitude,
        "longitude": settings.longitude,
        "start_date": day.isoformat(),
        "end_date": day.isoformat(),
        "hourly": ",".join(settings.air_quality_hourly_variables),
        "timezone": settings.timezone,
    }
    response = requests.get(settings.air_quality_url, params=params, timeout=60)
    response.raise_for_status()
    return response.json()
