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
    media_type = "image/jpeg"
    if key.lower().endswith(".png"):
        media_type = "image/png"
    return FileResponse(path, media_type=media_type)