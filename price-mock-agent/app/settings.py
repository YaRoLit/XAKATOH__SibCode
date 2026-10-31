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
    config_path: str = "/app/config/config.yaml"
    poll_interval_sec: int = 5
    log_level: str = "INFO"


def load_yaml_config(path: str | None = None) -> dict:
    cfg_path = Path(path or os.getenv("CONFIG_PATH", "/app/config/config.yaml"))
    if not cfg_path.exists():
        cfg_path = Path(__file__).resolve().parent.parent / "config" / "config.yaml"
    with cfg_path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


settings = Settings()
yaml_config = load_yaml_config(settings.config_path)


def prompt_text() -> tuple[str, str]:
    block = yaml_config.get("prompt") or {}
    return str(block.get("version") or "price-mock-p1.0"), str(block.get("text") or "").strip()
