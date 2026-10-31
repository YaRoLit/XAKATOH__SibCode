import os
from pathlib import Path

from app.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

_s3_client = None


def _get_s3_client():
    global _s3_client
    if _s3_client is None:
        import boto3
        from botocore.client import Config as BotoConfig
        _s3_client = boto3.client(
            "s3",
            endpoint_url=settings.storage.endpoint,
            aws_access_key_id=settings.storage.access_key,
            aws_secret_access_key=settings.storage.secret_key,
            config=BotoConfig(signature_version="s3v4"),
        )
    return _s3_client


def _local_path(key: str) -> Path:
    return Path(settings.storage.local_base_dir) / settings.storage.bucket / key


# --- Public API ---

def ensure_bucket() -> None:
    if settings.storage.backend == "local":
        d = Path(settings.storage.local_base_dir) / settings.storage.bucket
        d.mkdir(parents=True, exist_ok=True)
        log.debug("storage[local]: ensured dir %s", d)
    else:
        client = _get_s3_client()
        try:
            client.head_bucket(Bucket=settings.storage.bucket)
        except Exception:
            client.create_bucket(Bucket=settings.storage.bucket)
            log.debug("storage[s3]: bucket %s created", settings.storage.bucket)


def upload(key: str, data: bytes) -> None:
    if settings.storage.backend == "local":
        path = _local_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        log.debug("storage[local]: wrote %s (%d bytes)", path, len(data))
    else:
        _get_s3_client().put_object(Bucket=settings.storage.bucket, Key=key, Body=data)
        log.debug("storage[s3]: uploaded %s (%d bytes)", key, len(data))


def file_path(key: str) -> Path | None:
    """Путь к локальному файлу (только для backend=local). Иначе None."""
    if settings.storage.backend != "local":
        return None
    p = _local_path(key)
    return p if p.exists() else None


def presigned(key: str, expires: int = 3600) -> str:
    """
    Для local: возвращает публичный URL на эндпоинт раздачи.
    Для s3: обычный presigned URL.
    """
    if settings.storage.backend == "local":
        base = settings.public_api_base_url.rstrip("/")
        return f"{base}/api/v1/storage/{settings.storage.bucket}/{key}"
    return _get_s3_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.storage.bucket, "Key": key},
        ExpiresIn=expires,
    )