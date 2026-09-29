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
    JWT_ISSUER: str = "threshold"
    JWT_AUDIENCE: str = "threshold-api"

    MAX_REQUEST_BODY_BYTES: int = 1048576
    RATE_LIMIT_PER_MINUTE: int = 300
    AUTH_RATE_LIMIT_PER_MINUTE: int = 20
    WEBHOOK_RATE_LIMIT_PER_MINUTE: int = 600
    TRUST_PROXY_HEADERS: bool = False

    WEBHOOK_SIGNING_SECRET: str = ""

    CORS_ORIGINS: str = "http://localhost:5173"
    INTEGRATION_ALLOWED_HOSTS: str = ""
    OUTBOX_LEASE_SECONDS: int = 60
    OUTBOX_BATCH_SIZE: int = 100
    EVENT_PROCESSING_LEASE_SECONDS: int = 300
    ACTION_EXECUTION_LEASE_SECONDS: int = 120

    PUBLIC_APP_URL: str = "http://localhost:5173"
    BILLING_STRIPE_SECRET_REF: str = ""
    BILLING_STRIPE_WEBHOOK_SECRET_REF: str = ""
    STRIPE_STARTER_PRICE_ID: str = ""
    STRIPE_BUSINESS_PRICE_ID: str = ""

    SHOPIFY_CLIENT_ID: str = ""
    SHOPIFY_CLIENT_SECRET: str = ""
    SHOPIFY_SCOPES: str = "read_orders,read_customers,write_orders"
    SHOPIFY_OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/v1/commercial/shopify/callback"
    SHOPIFY_API_VERSION: str = "2026-07"
    OAUTH_SECRET_SINK_URL: str = ""
    OAUTH_SECRET_SINK_AUTH_REF: str = ""

    BETA_ALLOW_MOCK_AI: bool = False
    BETA_LAST_RESTORE_DRILL_AT: str = ""
    BETA_MAX_RESTORE_DRILL_AGE_DAYS: int = 30
    BETA_ALERTING_CONFIGURED: bool = False
    BETA_ONCALL_OWNER: str = ""

    def validate_runtime_secrets(self) -> None:
        if self.APP_ENV in {"staging", "production"}:
            if not self.SECRET_KEY or len(self.SECRET_KEY) < 32:
                raise ValueError("SECRET_KEY must be set to a strong value outside development")
            if "*" in self.cors_origins_list:
                raise ValueError("Wildcard CORS origins are forbidden outside development")
            if self.PUBLIC_APP_URL.startswith("http://"):
                raise ValueError("PUBLIC_APP_URL must use HTTPS outside development")
            if not self.WEBHOOK_SIGNING_SECRET or len(self.WEBHOOK_SIGNING_SECRET) < 32:
                raise ValueError(
                    "WEBHOOK_SIGNING_SECRET must be set to a strong value outside development"
                )

    def stripe_price_for_plan(self, plan: str) -> str:
        if plan == "starter":
            return self.STRIPE_STARTER_PRICE_ID
        if plan == "business":
            return self.STRIPE_BUSINESS_PRICE_ID
        return ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def integration_allowed_hosts_list(self) -> set[str]:
        return {
            host.strip().lower()
            for host in self.INTEGRATION_ALLOWED_HOSTS.split(",")
            if host.strip()
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
