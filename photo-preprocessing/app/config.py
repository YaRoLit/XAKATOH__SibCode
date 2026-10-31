from pydantic_settings import BaseSettings, SettingsConfigDict


class ValidationSettings(BaseSettings):
    min_width: int = 1920
    min_height: int = 1080
    altitude_min_m: float = 10.0
    altitude_max_m: float = 120.0
    min_coverage: float = 0.85
    gps_buffer_m: float = 7.0
    file_timeout_sec: float = 30.0 


class QualitySettings(BaseSettings):
    enabled: bool = True
    blur_threshold: float = 100.0
    brightness_min: float = 30.0
    brightness_max: float = 225.0
    min_std: float = 5.0


class DedupSettings(BaseSettings):
    enabled: bool = True


class IdempotencySettings(BaseSettings):
    enabled: bool = True


class PreviewSettings(BaseSettings):
    max_side: int = 1024
    jpeg_quality: int = 80


class StorageSettings(BaseSettings):
    backend: str = "local"                # "local" | "s3"
    local_base_dir: str = "/s3-storage"
    # s3 fields — используются только при backend="s3"
    endpoint: str = "http://minio:9000"
    access_key: str = "minioadmin"
    secret_key: str = "minioadmin123"
    bucket: str = "dronemon"


class DbSettings(BaseSettings):
    dsn: str = "postgresql+asyncpg://admin:secret@db:5432/dronemon"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__", env_file=".env", extra="ignore")

    log_level: str = "DEBUG"
    upload_dir: str = "/tmp/uploads"
    public_api_base_url: str = "http://api.yarolit.ru"
    validation: ValidationSettings = ValidationSettings()
    quality: QualitySettings = QualitySettings()
    dedup: DedupSettings = DedupSettings()
    idempotency: IdempotencySettings = IdempotencySettings()
    preview: PreviewSettings = PreviewSettings()
    storage: StorageSettings = StorageSettings()
    db: DbSettings = DbSettings()
    api_token: str = "changeme"


settings = Settings()