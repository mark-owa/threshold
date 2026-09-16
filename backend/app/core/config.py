from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_ENV: str = "development"
    APP_NAME: str = "Threshold"
    APP_VERSION: str = "0.1.0"
    SECRET_KEY: str = ""
    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str = "postgresql+psycopg://threshold:threshold@localhost:5432/threshold"

    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    AI_PROVIDER: str = "mock"
    AI_MODEL: str | None = None
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    WEBHOOK_SIGNING_SECRET: str = ""

    CORS_ORIGINS: str = "http://localhost:5173"

    def validate_runtime_secrets(self) -> None:
        if self.APP_ENV in {"staging", "production"}:
            if not self.SECRET_KEY or len(self.SECRET_KEY) < 32:
                raise ValueError("SECRET_KEY must be set to a strong value outside development")
            if not self.WEBHOOK_SIGNING_SECRET or len(self.WEBHOOK_SIGNING_SECRET) < 32:
                raise ValueError(
                    "WEBHOOK_SIGNING_SECRET must be set to a strong value outside development"
                )

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
