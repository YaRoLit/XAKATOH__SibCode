from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__", env_file=".env", extra="ignore")

    log_level: str = "DEBUG"
    db_dsn: str = "postgresql+asyncpg://admin:secret@db:5432/dronemon"
    jwt_secret: str = "change-me-hackathon-secret"
    jwt_expire_hours: int = 12
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    storage_public_base: str = "https://api.yarolit.ru/drones/api/v1/storage/dronemon"


settings = Settings()
