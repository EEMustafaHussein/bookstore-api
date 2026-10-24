from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    secret_key: str = Field(min_length=32)
    database_url: str = f"sqlite:///{(BASE_DIR / 'dreams.db').as_posix()}"
    debug: bool = False

    # Set to true when the site is served over HTTPS so cookies are never sent in clear text.
    cookie_secure: bool = False
    # Public address of the site, used for payment return links and the sitemap.
    # On Render it falls back to the address Render gives the service.
    base_url: str = Field(
        default="http://localhost:8000",
        validation_alias=AliasChoices("BASE_URL", "RENDER_EXTERNAL_URL"),
    )
    media_dir: Path = BASE_DIR / "media"
    # "disk" keeps photos in media_dir; "database" keeps them inside the database, for free
    # hosting where files on disk are wiped at every restart.
    media_storage: Literal["disk", "database"] = "disk"
    max_upload_mb: int = 8

    # The owner account is created on first start when these are set.
    owner_email: str | None = None
    owner_password: str | None = None
    owner_name: str = "صاحب المتجر"

    # Card payments (Mastercard, Visa, Apple Pay, Google Pay) through Stripe Checkout.
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_currency: str = "usd"
    # How many units of the shop currency equal one unit of the Stripe currency
    # (for example 1310 dinars = 1 dollar). Use 1 when both currencies are the same.
    stripe_exchange_rate: float = 1310.0

    # Simulated card payments for trying the store locally. Never enable it on a live site.
    payment_demo_mode: bool = False

    @field_validator("database_url")
    @classmethod
    def _default_when_blank(cls, value: str) -> str:
        return value.strip() or cls.model_fields["database_url"].default

    @property
    def stripe_enabled(self) -> bool:
        return bool(self.stripe_secret_key)

    @property
    def card_payments_enabled(self) -> bool:
        return self.stripe_enabled or self.payment_demo_mode


settings = Settings()
