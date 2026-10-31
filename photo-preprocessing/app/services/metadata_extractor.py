import io
import re

from PIL import Image

from app.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

SENSOR_SIZE = {"FC7303": (6.17, 4.55)}
DEFAULT_SENSOR = (6.17, 4.55)


def _dms_to_dec(dms, ref: str) -> float:
    d, m, s = (v[0] / v[1] if isinstance(v, tuple) else float(v) for v in dms)
    dec = d + m / 60.0 + s / 3600.0
    return -dec if ref in ("S", "W") else dec


def extract(file_bytes: bytes) -> dict:
    """Возвращает {"metadata": {...}, "errors": [str]}"""
    meta: dict = {}
    errors: list[str] = []
    try:
        img = Image.open(io.BytesIO(file_bytes))
        w, h = img.size
        meta["image"] = {"width": w, "height": h}
        if w < settings.validation.min_width or h < settings.validation.min_height:
            errors.append(f"Разрешение {w}x{h} ниже минимального "
                          f"{settings.validation.min_width}x{settings.validation.min_height}")

        exif = img._getexif() or {}
        gps = exif.get(34853)
        if not gps or 2 not in gps or 4 not in gps:
            errors.append("Отсутствуют GPS-координаты")
        else:
            meta["coordinates"] = {"lat": _dms_to_dec(gps[2], gps.get(1, "N")),
                                   "lon": _dms_to_dec(gps[4], gps.get(3, "E"))}

        focal = exif.get(37386)
        focal = focal[0] / focal[1] if isinstance(focal, tuple) and focal else 4.5
        model = exif.get(272, "FC7303")
        sw, sh = SENSOR_SIZE.get(model, DEFAULT_SENSOR)
        meta["camera"] = {"focal_length": focal, "model": model,
                          "sensor_width_mm": sw, "sensor_height_mm": sh}
        if 36867 in exif:
            meta["datetime_original"] = exif[36867]

        xmp = img.info.get("xmp", b"")
        xmp = xmp.decode("utf-8", errors="ignore") if isinstance(xmp, bytes) else (xmp or "")
        alt = re.search(r'dji:RelativeAltitude="([^"]+)"', xmp)
        if alt:
            rel = float(alt.group(1))
            meta["altitude"] = {"relative": rel}
            # Временно не проверяем высоту: RelativeAltitude у части снимков некорректна
            # и отсекает валидные фото (отрицательные / околонулевые значения).
            # if not alt:
            #     errors.append("Отсутствует высота полета (RelativeAltitude)")
            # elif not (settings.validation.altitude_min_m <= rel <= settings.validation.altitude_max_m):
            #     errors.append(
            #         f"Высота съемки {rel:.1f} м вне диапазона "
            #         f"{settings.validation.altitude_min_m}-{settings.validation.altitude_max_m} м"
            #     )

        yaw = re.search(r'dji:GimbalYawDegree="([^"]+)"', xmp)
        pitch = re.search(r'dji:GimbalPitchDegree="([^"]+)"', xmp)
        roll = re.search(r'dji:GimbalRollDegree="([^"]+)"', xmp)
        meta["orientation"] = {
            "yaw": float(yaw.group(1)) if yaw else 0.0,
            "pitch": float(pitch.group(1)) if pitch else -90.0,
            "roll": float(roll.group(1)) if roll else 0.0,
        }
    except Exception as e:  # битый файл и т.п.
        errors.append(f"Ошибка чтения файла: {e}")
        log.debug("extractor: file read failed: %s", e)

    log.debug("extractor: errors=%s meta_keys=%s", errors, list(meta.keys()))
    return {"metadata": meta, "errors": errors}