from pathlib import Path

from app.settings import settings


def file_path(key: str | None) -> Path | None:
    if not key:
        return None
    path = Path(settings.storage_base_dir) / settings.storage_bucket / key
    return path if path.exists() else None


def write_bytes(key: str, data: bytes) -> str:
    path = Path(settings.storage_base_dir) / settings.storage_bucket / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return key


def public_url(key: str | None) -> str | None:
    if not key:
        return None
    base = settings.report_public_base.rstrip("/")
    return f"{base}/{key.lstrip('/')}"
