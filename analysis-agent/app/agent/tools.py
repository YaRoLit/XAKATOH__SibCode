import base64
import io
from pathlib import Path

from PIL import Image

from app.settings import yaml_config


def crop_image_func(image_path: str, reason: str, xmin: int, ymin: int, xmax: int, ymax: int) -> str:
    """Путь к изображению передаётся первым аргументом из состояния графа."""
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


CROP_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "crop_image_tool",
        "description": (
            "Вырезает фрагмент изображения для детального рассмотрения. "
            "Координаты нормализованные 0-1000. Максимальная площадь кропа 300000."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Что рассматриваем и почему"},
                "xmin": {"type": "integer"},
                "ymin": {"type": "integer"},
                "xmax": {"type": "integer"},
                "ymax": {"type": "integer"},
            },
            "required": ["reason", "xmin", "ymin", "xmax", "ymax"],
            "additionalProperties": False,
        },
        "strict": True,
    },
}
