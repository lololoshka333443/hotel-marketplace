"""Application configuration.

All settings come from environment / .env. No magic constants here —
legal/business parameters live in `app/config/legal.py` and `app/config/payment.py`.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ----- App -----
    app_env: str = Field(default="local")
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000)
    log_level: str = Field(default="info")

    # ----- Database -----
    database_url: str = "postgresql://hotel_user:hotel_pass@localhost:5432/hotel_mp"

    # ----- Redis -----
    redis_url: str = Field(default="redis://localhost:6379/0")

    # ----- Auth -----
    jwt_secret: str = Field(default="CHANGE_ME_SUPER_SECRET_32_PLUS_CHARS_LONG")
    jwt_algorithm: str = Field(default="HS256")
    access_token_ttl_min: int = Field(default=60)

    # ----- Booking core -----
    hold_ttl_min: int = Field(default=15)

    # ----- Payment -----
    payment_mode: str = Field(default="stub")

    # ----- Telegram -----
    telegram_bot_token: str = Field(default="")

    # ----- Sentry -----
    sentry_dsn: str = Field(default="")

    @property
    def is_dev(self) -> bool:
        return self.app_env in ("local", "dev", "test")

    @property
    def project_root(self) -> Path:
        return PROJECT_ROOT

    @property
    def test_dsn(self) -> str:
        """asyncpg connection string (no +scheme, plain postgresql://)."""
        return self.database_url


settings = Settings()
