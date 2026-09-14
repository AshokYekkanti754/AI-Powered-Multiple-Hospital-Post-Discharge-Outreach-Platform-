from datetime import datetime, time, timezone
from app.services.retry_calculator import next_retry_time, retry_delay_minutes, schedule_within_calling_hours


def test_retry_delays_follow_required_schedule():
    assert [retry_delay_minutes(i) for i in (1, 2, 3)] == [15, 45, 120]


def test_retry_rolls_to_next_business_day_before_calling_window():
    now = datetime(2026, 9, 12, 19, 50, tzinfo=timezone.utc)
    result = next_retry_time(now, attempt_number=1, timezone_name="UTC", calling_hours_start=time(8), calling_hours_end=time(20))
    assert result == datetime(2026, 9, 14, 8, 0, tzinfo=timezone.utc)


def test_in_window_time_is_preserved():
    now = datetime(2026, 9, 14, 10, 0, tzinfo=timezone.utc)
    result = schedule_within_calling_hours(now, timezone_name="UTC", calling_hours_start=time(8), calling_hours_end=time(20))
    assert result == now
