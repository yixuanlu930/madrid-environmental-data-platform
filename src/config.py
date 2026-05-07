import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y"}


@dataclass(frozen=True)
class Settings:
    data_dir: str = os.getenv("DATA_DIR", "/app/data")
    latitude: float = float(os.getenv("MADRID_LATITUDE", "40.4168"))
    longitude: float = float(os.getenv("MADRID_LONGITUDE", "-3.7038"))
    timezone: str = os.getenv("TIMEZONE", "Europe/Madrid")

    minio_endpoint: str = os.getenv("MINIO_ENDPOINT", "minio:9000")
    minio_bucket: str = os.getenv("MINIO_BUCKET", "madrid-environment")
    minio_access_key: str = os.getenv("MINIO_ROOT_USER", "minioadmin")
    minio_secret_key: str = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
    minio_secure: bool = _env_bool("MINIO_SECURE", False)

    madrid_air_csv_url: str = os.getenv(
        "MADRID_AIR_CSV_URL",
        "https://datos.madrid.es/dataset/300755-0-calidad-aire-tiempo-real-acumula/resource/300755-0-calidad-aire-tiempo-real-acumula/download/300755-0-calidad-aire-tiempo-real-acumula.csv",
    )
    etl_port: int = int(os.getenv("ETL_PORT", "8000"))


settings = Settings()
