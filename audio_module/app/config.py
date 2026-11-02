"""
Централизованная конфигурация приложения.
Загружает переменные из .env файла с валидацией через Pydantic.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """
    Все настройки приложения. Значения берутся из переменных окружения
    или из файла .env в корне проекта.
    """

    # ── MongoDB ───────────────────────────────────────────
    MONGO_URI: str = "mongodb://localhost:27017"
    MONGO_DB_NAME: str = "interview_platform"

    # ── Supabase / PostgreSQL ─────────────────────────────
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None

    # ── Redis ─────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_TTL_SECONDS: int = 3600  # 1 час по умолчанию

    # ── RabbitMQ ──────────────────────────────────────────
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    AUDIO_QUEUE_NAME: str = "audio_analysis_queue"
    TEXT_QUEUE_NAME: str = "text_analysis_queue"
    WORKER_PREFETCH_COUNT: int = 1

    # ── Object Storage ────────────────────────────────────
    STORAGE_PROVIDER: str = "local_dev"  # local_dev | s3 | minio
    STORAGE_BASE_PATH: str = "./storage"

    # S3 / MinIO
    S3_ENDPOINT_URL: Optional[str] = None
    S3_ACCESS_KEY: Optional[str] = None
    S3_SECRET_KEY: Optional[str] = None
    S3_BUCKET_NAME: str = "interview-files"
    S3_REGION: str = "us-east-1"

    class Config:
        import os as _os
        env_file = _os.path.join(
            _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
            ".env",
        )
        env_file_encoding = "utf-8"
        extra = "ignore"

    # ── Helpers ───────────────────────────────────────────

    @property
    def supabase_enabled(self) -> bool:
        """Supabase доступен только если оба ключа заданы."""
        return bool(self.SUPABASE_URL and self.SUPABASE_KEY)

    @property
    def mongo_enabled(self) -> bool:
        """MongoDB считается доступным если URI задан."""
        return bool(self.MONGO_URI)

    @property
    def redis_enabled(self) -> bool:
        """Redis считается доступным если URL задан."""
        return bool(self.REDIS_URL)

    @property
    def rabbitmq_enabled(self) -> bool:
        """RabbitMQ считается доступным если URL задан."""
        return bool(self.RABBITMQ_URL)


# Глобальный синглтон
settings = Settings()
