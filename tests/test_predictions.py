from datetime import datetime, time, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from huckleberry_homepod.app import is_quiet_time
from huckleberry_homepod.predictions import (
    epoch_datetime,
    feed_reminder,
    reminder_value_minutes,
    sleep_reminders,
)

TZ = "America/Los_Angeles"


def test_epoch_datetime_accepts_seconds_and_milliseconds() -> None:
    seconds = 1_800_000_000
    assert epoch_datetime(seconds, TZ) == epoch_datetime(seconds * 1000, TZ)


def test_sleep_reminder_selects_future_values_and_ignores_nulls() -> None:
    now = datetime(2027, 1, 1, 10, 0, tzinfo=ZoneInfo(TZ))
    future = now + timedelta(hours=1)
    result = sleep_reminders(
        {"0": None, "1": int(future.timestamp() * 1000)},
        now=now,
        timezone=TZ,
        lead_minutes=15,
    )
    assert len(result) == 1
    assert result[0].announce_at == future - timedelta(minutes=15)


def test_sleep_reminder_uses_selected_nap_schedule() -> None:
    now = datetime(2027, 1, 1, 10, 0, tzinfo=ZoneInfo(TZ))
    result = sleep_reminders(
        {
            "2": int((now + timedelta(hours=1)).timestamp()),
            "3": int((now + timedelta(minutes=50)).timestamp()),
        },
        selected_nap_day=3,
        now=now,
        timezone=TZ,
        lead_minutes=15,
        announce_lead_minutes=16,
    )
    assert len(result) == 1
    assert result[0].key.startswith("sleep:3:")
    assert result[0].announce_at == now + timedelta(minutes=34)
    assert "15分钟后" in result[0].message


def test_reminder_value_minutes_handles_common_representations() -> None:
    assert reminder_value_minutes(3) == 180
    assert reminder_value_minutes(180) == 180
    assert reminder_value_minutes(10_800) == 180
    assert reminder_value_minutes(10_800_000) == 180


def test_feed_reminder_uses_latest_nursing_or_bottle() -> None:
    now = datetime(2027, 1, 1, 10, 0, tzinfo=ZoneInfo(TZ))
    last_bottle = now - timedelta(hours=2)
    feed = SimpleNamespace(
        timer=SimpleNamespace(active=False),
        prefs=SimpleNamespace(
            lastNursing=SimpleNamespace(
                start=int((now - timedelta(hours=4)).timestamp())
            ),
            lastBottle=SimpleNamespace(start=int(last_bottle.timestamp())),
            reminderV2=None,
        ),
    )
    result = feed_reminder(
        feed,
        now=now,
        timezone=TZ,
        lead_minutes=30,
        announce_after_minutes=179,
        interval_override_minutes=210,
    )
    assert result is not None
    assert result.event_time == last_bottle + timedelta(hours=3, minutes=30)
    assert result.announce_at == last_bottle + timedelta(hours=2, minutes=59)
    assert "还有30分钟" in result.message


def test_feed_reminder_is_disabled_while_timer_active() -> None:
    feed = SimpleNamespace(timer=SimpleNamespace(active=True), prefs=SimpleNamespace())
    result = feed_reminder(
        feed,
        now=datetime.now(ZoneInfo(TZ)),
        timezone=TZ,
        lead_minutes=10,
        announce_after_minutes=179,
        interval_override_minutes=210,
    )
    assert result is None


def test_quiet_time_spans_midnight_with_exact_boundaries() -> None:
    def at(hour: int, minute: int = 0) -> datetime:
        return datetime(2027, 1, 1, hour, minute, tzinfo=ZoneInfo(TZ))

    start = time(19, 30)
    end = time(8)
    assert not is_quiet_time(at(19, 29), start, end)
    assert is_quiet_time(at(19, 30), start, end)
    assert is_quiet_time(at(0), start, end)
    assert is_quiet_time(at(7, 59), start, end)
    assert not is_quiet_time(at(8), start, end)
