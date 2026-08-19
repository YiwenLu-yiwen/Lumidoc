"""UTC time helpers with explicit timezone semantics."""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def utc_now_naive() -> datetime:
    """Return naive UTC for database columns declared without a timezone."""
    return utc_now().replace(tzinfo=None)


def as_utc_naive(value: datetime) -> datetime:
    """Normalize an aware or naive datetime for a UTC-naive database column."""
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)
