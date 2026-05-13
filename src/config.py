
import os
from dataclasses import dataclass


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y"}


def env_list(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    data_dir: str = os.getenv("DATA_DIR", "/app/data")
    latitude: float = float(os.getenv("MADRID_LATITUDE", "40.4168"))
    longitude: float = float(os.getenv("MADRID_LONGITUDE", "-3.7038"))
    timezone: str = os.getenv("TIMEZONE", "Europe/Madrid")

    historical_weather_url: str = os.getenv("HISTORICAL_WEATHER_URL", "https://archive-api.open-meteo.com/v1/archive")
    air_quality_url: str = os.getenv("AIR_QUALITY_URL", "https://air-quality-api.open-meteo.com/v1/air-quality")

    weather_hourly_variables: list[str] = None
    air_quality_hourly_variables: list[str] = None

    minio_endpoint: str = os.getenv("MINIO_ENDPOINT", "minio:9000")
    minio_bucket: str = os.getenv("MINIO_BUCKET", "madrid-openmeteo-environment")
    minio_access_key: str = os.getenv("MINIO_ROOT_USER", "minioadmin")
    minio_secret_key: str = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
    minio_secure: bool = env_bool("MINIO_SECURE", False)

    etl_port: int = int(os.getenv("ETL_PORT", "8000"))

    # PostgreSQL – capa analítica (Día 2)
    pg_host: str = os.getenv("POSTGRES_HOST", "postgres")
    pg_port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    pg_db: str = os.getenv("POSTGRES_DB", "madrid_env")
    pg_user: str = os.getenv("POSTGRES_USER", "madrid")
    pg_password: str = os.getenv("POSTGRES_PASSWORD", "madrid")

    def __post_init__(self):
        object.__setattr__(self, "weather_hourly_variables", env_list("WEATHER_HOURLY_VARIABLES", "temperature_2m,precipitation"))
        object.__setattr__(self, "air_quality_hourly_variables", env_list("AIR_QUALITY_HOURLY_VARIABLES", "ozone,carbon_dioxide"))


settings = Settings()
