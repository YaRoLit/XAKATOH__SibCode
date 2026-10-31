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


def render_on_demand(temp_path: str, metadata: dict, plot_corners: list) -> bytes:
    """
    Читает оригинал из temp_path, ресайзит до max_side, рисует границы и возвращает bytes.
    Ничего не сохраняет на диск.
    """
    img = cv2.imread(temp_path)
    if img is None:
        raise ValueError(f"Не удалось прочитать изображение: {temp_path}")
    
    h, w = img.shape[:2]
    
    # 1. Считаем координаты углов в пикселях оригинала
    corners_px = [_geo_to_px(p["lat"], p["lon"], metadata, w, h) for p in plot_corners]
    
    # 2. Ресайз до max_side (например, 1024)
    max_side = settings.preview.max_side
    scale = max_side / max(w, h)
    
    if scale < 1.0:
        new_w, new_h = int(w * scale), int(h * scale)
        img_resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        corners_scaled = [(int(x * scale), int(y * scale)) for x, y in corners_px]
    else:
        img_resized = img
        corners_scaled = [(int(x), int(y)) for x, y in corners_px]
    
    # 3. Рисуем периметр (красная линия) и углы (синие точки)
    pts = np.array(corners_scaled, dtype=np.int32)
    cv2.polylines(img_resized, [pts], isClosed=True, color=(0, 0, 255), thickness=3)
    for x, y in corners_scaled:
        cv2.circle(img_resized, (x, y), 6, (255, 0, 0), -1)
    
    # 4. Кодируем в JPEG
    ok, buf = cv2.imencode(".jpg", img_resized, [cv2.IMWRITE_JPEG_QUALITY, settings.preview.jpeg_quality])
    if not ok:
        raise ValueError("Ошибка кодирования изображения в JPEG")
    
    log.debug("preview: rendered on-demand from %s, scale=%.2f, size=%d bytes", temp_path, scale, len(buf))
    return buf.tobytes()