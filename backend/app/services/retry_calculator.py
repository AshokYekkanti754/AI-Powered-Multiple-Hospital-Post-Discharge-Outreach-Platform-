"""Retry delays and local hospital calling-window scheduling."""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


RETRY_DELAYS_MINUTES = (15, 45, 120)


def retry_delay_minutes(attempt_number: int) -> int:
    if attempt_number < 1:
        raise ValueError("attempt_number must be at least 1")
    return RETRY_DELAYS_MINUTES[min(attempt_number, len(RETRY_DELAYS_MINUTES)) - 1]


def schedule_within_calling_hours(
    scheduled_time: datetime,
    *,
    timezone_name: str,
    calling_hours_start: time,
    calling_hours_end: time,
) -> datetime:
    """Return the same instant if valid, otherwise next day's local start."""
    local = scheduled_time.astimezone(ZoneInfo(timezone_name)) if scheduled_time.tzinfo else scheduled_time.replace(tzinfo=ZoneInfo(timezone_name))
    if calling_hours_start <= local.time() <= calling_hours_end:
        return scheduled_time
    next_day = local.date() + timedelta(days=1)
    while next_day.weekday() >= 5:
        next_day += timedelta(days=1)
    return datetime.combine(next_day, calling_hours_start, tzinfo=ZoneInfo(timezone_name))


def next_retry_time(
    now: datetime,
    *,
    attempt_number: int,
    timezone_name: str,
    calling_hours_start: time,
    calling_hours_end: time,
) -> datetime:
    candidate = now + timedelta(minutes=retry_delay_minutes(attempt_number))
    return schedule_within_calling_hours(candidate, timezone_name=timezone_name, calling_hours_start=calling_hours_start, calling_hours_end=calling_hours_end)
