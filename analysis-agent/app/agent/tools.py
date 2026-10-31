import base64
import io
from pathlib import Path

from PIL import Image

from app.settings import yaml_config


def _photo_by_index(photos: list[dict], photo_index: int) -> dict | None:
    for photo in photos or []:
        if int(photo.get("index") or 0) == int(photo_index):
            return photo
    return None


def encode_image(image_path: str, max_side: int, quality: int) -> str:
    with Image.open(image_path) as img:
        img = img.convert("RGB")
        img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality, optimize=True)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")


def select_photo_func(photos: list[dict], photo_index: int, reason: str) -> str:
    photo = _photo_by_index(photos, photo_index)
    if photo is None:
        return f"Ошибка: фото {photo_index} нет в рабочей группе."
    path = photo.get("path")
    if not path or not Path(path).exists():
        return f"Ошибка: файл фото {photo_index} недоступен."
    image_cfg = yaml_config.get("image") or {}
    max_side = int(image_cfg.get("overview_max_side", 1024))
    return encode_image(path, max_side, 90)


def crop_image_func(image_path: str, reason: str, xmin: int, ymin: int, xmax: int, ymax: int) -> str:
    """Путь к изображению передаётся из состояния графа по photo_index."""
    image_cfg = yaml_config.get("image") or {}
    agent_cfg = yaml_config.get("agent") or {}
    max_area = int(agent_cfg.get("crop_max_area", 300000))
    padding = float(image_cfg.get("crop_padding", 0.10))
    max_side = int(image_cfg.get("crop_max_side", 1024))
    quality = int(image_cfg.get("crop_quality", 90))

    if xmin >= xmax:
        return f"Ошибка: xmin ({xmin}) должен быть меньше xmax ({xmax})"
    if ymin >= ymax:
        return f"Ошибка: ymin ({ymin}) должен быть меньше ymax ({ymax})"
    area = (xmax - xmin) * (ymax - ymin)
    if area > max_area:
        return f"Ошибка: кроп слишком большой (площадь {area}). Максимум {max_area}."
    if not image_path or not Path(image_path).exists():
        return f"Ошибка: файл изображения недоступен: {image_path}"

    try:
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            width, height = img.size
            x1 = int(xmin / 1000 * width)
            y1 = int(ymin / 1000 * height)
            x2 = int(xmax / 1000 * width)
            y2 = int(ymax / 1000 * height)
            pw = int((x2 - x1) * padding)
            ph = int((y2 - y1) * padding)
            x1 = max(0, x1 - pw)
            y1 = max(0, y1 - ph)
            x2 = min(width, x2 + pw)
            y2 = min(height, y2 + ph)
            crop = img.crop((x1, y1, x2, y2))
            crop.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            crop.save(buffer, format="JPEG", quality=quality, optimize=True)
            return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception as exc:
        return f"Ошибка: {exc}"


def crop_photo_func(photos: list[dict], photo_index: int, reason: str, xmin: int, ymin: int, xmax: int, ymax: int) -> str:
    photo = _photo_by_index(photos, photo_index)
    if photo is None:
        return f"Ошибка: фото {photo_index} нет в рабочей группе."
    return crop_image_func(photo.get("path") or "", reason, xmin, ymin, xmax, ymax)


def thumbnail_side(photo_count: int) -> int:
    multi = yaml_config.get("multi_photo") or {}
    budget = int(multi.get("thumbnail_pixel_budget", 2_000_000))
    n = max(int(photo_count or 1), 1)
    return int(max(256, min(1024, (budget / n) ** 0.5)))


SELECT_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "select_photo_tool",
        "description": (
            "Возвращает выбранное фото целиком (до 1024 по длинной стороне) для детального осмотра. "
            "photo_index — номер фото в группе (1 = самое раннее)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "photo_index": {"type": "integer", "description": "Номер фото, 1 = самое раннее"},
                "reason": {"type": "string", "description": "Почему нужно это фото целиком"},
            },
            "required": ["photo_index", "reason"],
            "additionalProperties": False,
        },
        "strict": True,
    },
}

CROP_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "crop_photo_tool",
        "description": (
            "Вырезает фрагмент выбранного фото. Координаты нормализованные 0-1000. "
            "Максимальная площадь кропа 300000. photo_index — номер фото в группе."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "photo_index": {"type": "integer", "description": "Номер фото, при одном снимке всегда 1"},
                "reason": {"type": "string", "description": "Что рассматриваем и почему"},
                "xmin": {"type": "integer"},
                "ymin": {"type": "integer"},
                "xmax": {"type": "integer"},
                "ymax": {"type": "integer"},
            },
            "required": ["photo_index", "reason", "xmin", "ymin", "xmax", "ymax"],
            "additionalProperties": False,
        },
        "strict": True,
    },
}

# Старое имя оставлено как алиас на случай старого промпта в кэше.
CROP_IMAGE_TOOL_SCHEMA = {
    **CROP_TOOL_SCHEMA,
    "function": {**CROP_TOOL_SCHEMA["function"], "name": "crop_image_tool"},
}
