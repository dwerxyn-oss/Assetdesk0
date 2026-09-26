"""Конфигурация из окружения. Секреты в код не записываются."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent


def _default_database_url() -> str:
    path = (ROOT_DIR / "data" / "assetdesk.db").as_posix()
    return f"sqlite+aiosqlite:///{path}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        str_strip_whitespace=True,
    )

    bot_token: str = ""
    admin_id: int = 0
    bot_username: str = ""
    support_username: str = "AssetDeskOriginal"

    timezone: str = "Europe/Moscow"

    first_withdraw_min: int = 15
    regular_withdraw_min: int = 15

    new_seller_limit_usd: int = 25
    regular_seller_limit_usd: int = 50
    trusted_seller_limit_usd: int = 100

    referral_reward: int = 2
    referral_daily_limit: int = 30
    daily_bonus: int = 2
    gift_transfer_text: str = ""

    database_url: str = ""

    @field_validator("bot_username", "support_username")
    @classmethod
    def strip_username(cls, value: str) -> str:
        return value.strip().lstrip("@")

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Неизвестная таймзона: {value}") from exc
        return value

    def resolved_database_url(self) -> str:
        if self.database_url.strip():
            return self.database_url.strip()
        return _default_database_url()

    def seller_limit_for_level(self, level: str) -> int:
        limits = {
            "new": self.new_seller_limit_usd,
            "regular": self.regular_seller_limit_usd,
            "trusted": self.trusted_seller_limit_usd,
        }
        if level not in limits:
            raise ValueError(f"Неизвестный уровень продавца: {level}")
        return limits[level]

    def assert_runtime(self) -> None:
        missing: list[str] = []
        if not self.bot_token:
            missing.append("BOT_TOKEN")
        if self.admin_id <= 0:
            missing.append("ADMIN_ID")
        if not self.bot_username:
            missing.append("BOT_USERNAME")
        if not self.support_username:
            missing.append("SUPPORT_USERNAME")
        if missing:
            joined = ", ".join(missing)
            raise SystemExit(f"Заполните в .env: {joined}")

        if self.first_withdraw_min <= 0 or self.regular_withdraw_min <= 0:
            raise SystemExit("FIRST_WITHDRAW_MIN и REGULAR_WITHDRAW_MIN должны быть больше 0")
        if self.referral_reward < 0 or self.daily_bonus < 0:
            raise SystemExit("REFERRAL_REWARD и DAILY_BONUS не могут быть отрицательными")
        if self.referral_daily_limit <= 0:
            raise SystemExit("REFERRAL_DAILY_LIMIT должен быть больше 0")
        for name in (
            "new_seller_limit_usd",
            "regular_seller_limit_usd",
            "trusted_seller_limit_usd",
        ):
            if getattr(self, name) <= 0:
                raise SystemExit(f"{name.upper()} должен быть больше 0")


@lru_cache
def get_settings() -> Settings:
    return Settings()
