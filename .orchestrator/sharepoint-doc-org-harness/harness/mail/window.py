from __future__ import annotations

from datetime import datetime, timedelta, timezone


def first_pass_since(
    now: datetime | None = None, *, lookback_days: int = 90
) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current - timedelta(days=lookback_days)


def in_first_pass(
    received_at: datetime,
    *,
    now: datetime | None = None,
    lookback_days: int = 90,
) -> bool:
    since = first_pass_since(now, lookback_days=lookback_days)
    received = received_at
    if received.tzinfo is None:
        received = received.replace(tzinfo=timezone.utc)
    return received >= since
