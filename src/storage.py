
from __future__ import annotations
import time
from pathlib import Path
from minio import Minio
from src.config import settings
from src.utils import list_files


def get_minio_client() -> Minio:
    return Minio(settings.minio_endpoint, access_key=settings.minio_access_key, secret_key=settings.minio_secret_key, secure=settings.minio_secure)


def ensure_bucket(client: Minio) -> None:
    last_error = None
    for _ in range(10):
        try:
            if not client.bucket_exists(settings.minio_bucket):
                client.make_bucket(settings.minio_bucket)
            return
        except Exception as exc:
            last_error = exc
            time.sleep(2)
    raise RuntimeError(f"Could not connect to MinIO or create bucket: {last_error}")


def upload_pipeline_outputs(data_dir: str | Path, day_string: str) -> list[str]:
    data_dir = Path(data_dir)
    client = get_minio_client()
    ensure_bucket(client)
    uploaded: list[str] = []
    for path in list_files(data_dir):
        if day_string not in str(path):
            continue
        object_name = str(path.relative_to(data_dir)).replace('\\', '/')
        client.fput_object(settings.minio_bucket, object_name, str(path))
        uploaded.append(object_name)
    return sorted(uploaded)
