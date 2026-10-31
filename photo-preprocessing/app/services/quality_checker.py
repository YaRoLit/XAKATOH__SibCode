import cv2
import numpy as np

from app.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


def check(file_bytes: bytes) -> list[str]:
    if not settings.quality.enabled:
        return []
    arr = cv2.imdecode(np.frombuffer(file_bytes, np.uint8), cv2.IMREAD_COLOR)
    if arr is None:
        return ["Файл не декодируется как изображение"]
    gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
    mean, std = float(gray.mean()), float(gray.std())
    errors = []
    if mean < settings.quality.brightness_min:
        errors.append(f"Черный/темный кадр (яркость {mean:.1f})")
    if mean > settings.quality.brightness_max:
        errors.append(f"Пересвеченный кадр (яркость {mean:.1f})")
    if std < settings.quality.min_std:
        errors.append(f"Одородный кадр (std {std:.1f})")

    scale = 800 / max(gray.shape)
    if scale < 1:
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if blur < settings.quality.blur_threshold:
        errors.append(f"Размытое изображение (blur score {blur:.1f} < {settings.quality.blur_threshold})")
    log.debug("quality: mean=%.1f std=%.1f blur=%.1f errors=%s", mean, std, blur, errors)
    return errors