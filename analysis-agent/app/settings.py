import os
from pathlib import Path

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://admin:secret@db:5432/dronemon"
    llm_base_url: str = "https://llm.yarolit.ru/v1"
    llm_api_key: str = "change-me"
    llm_model: str = "local"
    storage_base_dir: str = "/s3-storage"
    storage_bucket: str = "dronemon"
    report_public_base: str = "https://api.yarolit.ru/drones/api/v1/storage/dronemon"
    config_path: str = "/app/config/config.yaml"
    log_level: str = "INFO"


def load_yaml_config(path: str | None = None) -> dict:
    cfg_path = Path(path or os.getenv("CONFIG_PATH", "/app/config/config.yaml"))
    if not cfg_path.exists():
        cfg_path = Path(__file__).resolve().parent.parent / "config" / "config.yaml"
    with cfg_path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


settings = Settings()
yaml_config = load_yaml_config(settings.config_path)


def stages_text(cfg: dict | None = None) -> str:
    cfg = cfg or yaml_config
    lines = [f"- {item['id']}: {item['name']}" for item in cfg.get("stages", [])]
    return "\n".join(lines)


def scale_text(cfg: dict | None = None) -> str:
    cfg = cfg or yaml_config
    return str(cfg.get("calibration_scale") or "").strip()


def multi_photo_block(photo_count: int, cfg: dict | None = None) -> str:
    if photo_count <= 1:
        return ""
    cfg = cfg or yaml_config
    block = ((cfg.get("multi_photo") or {}).get("prompt_block") or "").strip()
    return block.replace("{{N}}", str(photo_count))


def render_prompt(kind: str, cfg: dict | None = None, photo_count: int = 1) -> tuple[str, str]:
    cfg = cfg or yaml_config
    block = cfg["prompts"][kind]
    text = (
        block["text"]
        .replace("{{STAGES}}", stages_text(cfg))
        .replace("{{SCALE}}", scale_text(cfg))
        .replace("{{MULTI_PHOTO}}", multi_photo_block(photo_count, cfg))
    )
    return block["version"], text


def stage_name(stage_id: int, cfg: dict | None = None) -> str:
    cfg = cfg or yaml_config
    for item in cfg.get("stages", []):
        if item.get("id") == stage_id:
            return item["name"]
    return f"этап {stage_id}"


def format_stage_label(ids: list[int] | None, cfg: dict | None = None) -> str | None:
    if not ids:
        return None
    return " → ".join(str(i) for i in ids)
