from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.services import storage

router = APIRouter(prefix="/api/v1/storage", tags=["storage"])


@router.get("/{bucket}/{key:path}")
async def get_file(bucket: str, key: str):
    # В локальном режиме bucket игнорируем (используем из конфига),
    # но оставляем в URL для совместимости с presigned-форматом.
    path = storage.file_path(key)
    if path is None:
        raise HTTPException(status_code=404, detail="File not found")
    media_type = "application/octet-stream"
    lower = key.lower()
    if lower.endswith(".jpg") or lower.endswith(".jpeg"):
        media_type = "image/jpeg"
    elif lower.endswith(".png"):
        media_type = "image/png"
    elif lower.endswith(".html"):
        media_type = "text/html; charset=utf-8"
    return FileResponse(path, media_type=media_type)