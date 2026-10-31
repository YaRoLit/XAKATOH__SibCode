import math
import cv2
import numpy as np

from app.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


def _geo_to_px(lat: float, lon: float, meta: dict, w: int, h: int) -> tuple[float, float]:
    """Конвертирует гео-координаты угла участка в пиксели исходного изображения."""
    lat0, lon0 = meta["coordinates"]["lat"], meta["coordinates"]["lon"]
    alt = meta["altitude"]["relative"]
    cam = meta["camera"]
    
    # GSD (Ground Sample Distance) в метрах на пиксель
    gsd_x = (cam["sensor_width_mm"] * alt) / (cam["focal_length"] * w)
    gsd_y = (cam["sensor_height_mm"] * alt) / (cam["focal_length"] * h)
    
    # Смещение в метрах от центра снимка
    e = (lon - lon0) * 111_000.0 * math.cos(math.radians(lat0))
    n = (lat - lat0) * 111_000.0
    
    # Учет поворота камеры (Yaw)
    yaw = math.radians(meta["orientation"]["yaw"])
    px = (e * math.cos(yaw) + n * math.sin(yaw)) / gsd_x
    py = (-e * math.sin(yaw) + n * math.cos(yaw)) / gsd_y
    
    return (w / 2) + px, (h / 2) + py


def _can_project(metadata: dict | None) -> bool:
    if not metadata:
        return False
    coords = metadata.get("coordinates") or {}
    alt = metadata.get("altitude") or {}
    cam = metadata.get("camera") or {}
    return bool(coords.get("lat") is not None and coords.get("lon") is not None and alt.get("relative") and cam.get("focal_length"))


def render_on_demand(temp_path: str, metadata: dict | None, plot_corners: list | None) -> bytes:
    """Миниатюра из temp. Границы рисуются, если есть GPS-метаданные и 4+ точки."""
    img = cv2.imread(temp_path)
    if img is None:
        raise ValueError(f"Не удалось прочитать изображение: {temp_path}")

    h, w = img.shape[:2]
    max_side = settings.preview.max_side
    scale = max_side / max(w, h)
    if scale < 1.0:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    else:
        scale = 1.0

    corners = plot_corners or []
    if _can_project(metadata) and len(corners) >= 1:
        try:
            corners_px = [_geo_to_px(p["lat"], p["lon"], metadata, w, h) for p in corners]
            corners_scaled = [(int(x * scale), int(y * scale)) for x, y in corners_px]
            pts = np.array(corners_scaled, dtype=np.int32)
            if len(corners_scaled) >= 4:
                cv2.polylines(img, [pts], isClosed=True, color=(0, 0, 255), thickness=3)
            for x, y in corners_scaled:
                cv2.circle(img, (x, y), 8 if len(corners_scaled) == 1 else 6, (255, 0, 0), -1)
        except Exception as exc:
            log.debug("preview: skip overlay: %s", exc)

    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, settings.preview.jpeg_quality])
    if not ok:
        raise ValueError("Ошибка кодирования изображения в JPEG")
    return buf.tobytes()