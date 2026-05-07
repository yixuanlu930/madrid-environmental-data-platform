from pathlib import Path
from minio import Minio
from minio.error import S3Error

from src.config import settings
from src.utils import list_files


def get_minio_client() -> Minio:
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def ensure_bucket(client: Minio) -> None:
    if not client.bucket_exists(settings.minio_bucket):
        client.make_bucket(settings.minio_bucket)


def upload_file(client: Minio, local_path: Path, object_name: str) -> None:
    client.fput_object(settings.minio_bucket, object_name, str(local_path))


def upload_pipeline_outputs(data_dir: str | Path, day_string: str) -> list[str]:
    client = get_minio_client()
    ensure_bucket(client)

    uploaded: list[str] = []
    for path in list_files(data_dir):
        # Upload only files belonging to the current date execution.
        if day_string not in str(path):
            continue
        object_name = str(path.relative_to(data_dir)).replace("\\", "/")
        upload_file(client, path, object_name)
        uploaded.append(object_name)
    return uploaded
