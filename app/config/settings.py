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
    # Public origin used to build URLs handed to partners (iCal feeds, links).
    app_base_url: str = Field(default="http://localhost:8000")
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

    # ----- Channel sync -----
    # How often the iCal importer revisits a subscribed calendar.
    ical_sync_interval_sec: int = Field(default=900)

    # ----- Channel API rate limits -----
    # Per API key, separate buckets: a read burst is a nuisance, a write burst
    # is real bookings. Over the limit the channel gets 429 + Retry-After.
    channel_write_limit_per_min: int = Field(default=30)
    channel_read_limit_per_min: int = Field(default=120)
    # The window both buckets live in. Separate from the numbers so a test does
    # not have to sleep a whole minute.
    rate_limit_window_sec: int = Field(default=60)
    # Per webhook subscription: the worker never pushes a partner's hook faster
    # than this, so our queue spike cannot drown their server.
    webhook_rate_per_sec: int = Field(default=10)
    # How often the outbox worker claims a batch. Exposed for tests.
    outbox_poll_interval_sec: int = Field(default=15)

    # ----- Outbox backlog limit -----
    # A mass operation (bulk price load, an iCal import of a whole season) can
    # throw thousands of events at the queue; the worker drains it at
    # webhook_rate_per_sec per subscription. Beyond this depth, low-priority
    # events are shed instead of queued — see app/modules/outbox/backlog.py.
    # Bookings are never subject to this.
    outbox_max_pending: int = Field(default=2000)
    # How deep the queue has to be before the admin strip flags it as falling
    # behind, in seconds since the oldest pending event.
    outbox_lag_alert_sec: int = Field(default=300)

    # ----- Webhook delivery retention -----
    # webhook_delivery is partitioned by delivered_at, one partition a month,
    # and ages out on a schedule (app/modules/outbox/retention.py) — never in
    # a request, never wholesale.
    # Successes are the bulk of the table and only the proof of a delivery:
    # the booking itself is the source of truth, so they go first.
    webhook_delivery_success_days: int = Field(default=30)
    # Failures are kept far longer — this is the table reconciliation reads
    # when a partner claims a booking never arrived.
    webhook_delivery_failed_days: int = Field(default=365)
    # Partitions are created this many months ahead so a delivery never waits
    # on missing DDL.
    webhook_delivery_partition_ahead_months: int = Field(default=3)
    # How often the retention sweep runs (also tops up future partitions).
    retention_interval_sec: int = Field(default=3600)

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
