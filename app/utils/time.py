from __future__ import annotations

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from app.config import get_settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def now_in_tz() -> datetime:
    return datetime.now(ZoneInfo(get_settings().timezone))


def today_in_tz() -> date:
    return now_in_tz().date()


def start_of_today_utc() -> datetime:
    local = datetime.combine(today_in_tz(), time.min, tzinfo=ZoneInfo(get_settings().timezone))
    return local.astimezone(timezone.utc)


def format_local(value: datetime | None) -> str:
    if value is None:
        return "—"
    local = as_utc(value).astimezone(ZoneInfo(get_settings().timezone))
    return local.strftime("%d.%m.%Y %H:%M")


def format_local_date(value: datetime | None) -> str:
    if value is None:
        return "—"
    local = as_utc(value).astimezone(ZoneInfo(get_settings().timezone))
    return local.strftime("%d.%m.%Y")


def account_age_days(created_at: datetime, *, now: datetime | None = None) -> int:
    tz = ZoneInfo(get_settings().timezone)
    created = as_utc(created_at).astimezone(tz).date()
    current = as_utc(now).astimezone(tz).date() if now is not None else today_in_tz()
    return max(0, (current - created).days)
