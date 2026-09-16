from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Reminder:
    key: str
    kind: str
    event_time: datetime
    announce_at: datetime
    message: str


def epoch_datetime(value: float | int | None, timezone: str) -> datetime | None:
    if value is None:
        return None
    timestamp = float(value)
    if timestamp > 10_000_000_000:
        timestamp /= 1000
    if timestamp < 1_000_000_000:
        return None
    return datetime.fromtimestamp(timestamp, ZoneInfo(timezone))


def sleep_reminders(
    sweetspot_times: dict[str, float | int | None] | None,
    *,
    selected_nap_day: float | int | None = None,
    now: datetime,
    timezone: str,
    lead_minutes: int,
    announce_lead_minutes: int | None = None,
    baby_name: str = "宝宝",
) -> list[Reminder]:
    reminders: list[Reminder] = []
    times = sweetspot_times or {}
    if selected_nap_day is not None:
        selected_key = str(int(selected_nap_day))
        if selected_key in times:
            times = {selected_key: times[selected_key]}

    for slot, raw_time in times.items():
        event_time = epoch_datetime(raw_time, timezone)
        if event_time is None or event_time < now - timedelta(minutes=30):
            continue
        announce_at = event_time - timedelta(
            minutes=announce_lead_minutes or lead_minutes
        )
        reminders.append(
            Reminder(
                key=f"sleep:{slot}:{int(event_time.timestamp())}",
                kind="sleep",
                event_time=event_time,
                announce_at=announce_at,
                message=f"{baby_name}预计{lead_minutes}分钟后进入最佳睡眠时间",
            )
        )
    return sorted(reminders, key=lambda item: item.event_time)


def reminder_value_minutes(value: float | int | None) -> int | None:
    """Interpret Huckleberry's undocumented reminder interval representation."""
    if value is None or value <= 0:
        return None
    number = float(value)
    if number >= 360_000:  # JavaScript duration in milliseconds
        return round(number / 60_000)
    if number >= 1_800:  # duration in seconds
        return round(number / 60)
    if number <= 24:  # hours
        return round(number * 60)
    return round(number)  # minutes


def feed_reminder(
    feed: Any,
    *,
    now: datetime,
    timezone: str,
    lead_minutes: int,
    announce_after_minutes: int | None,
    interval_override_minutes: int | None,
    baby_name: str = "宝宝",
) -> Reminder | None:
    prefs = getattr(feed, "prefs", None)
    timer = getattr(feed, "timer", None)
    if prefs is None or (timer is not None and getattr(timer, "active", False)):
        return None

    starts = [
        getattr(getattr(prefs, "lastNursing", None), "start", None),
        getattr(getattr(prefs, "lastBottle", None), "start", None),
    ]
    last_feed = max(
        (dt for value in starts if (dt := epoch_datetime(value, timezone)) is not None),
        default=None,
    )
    reminder = getattr(getattr(prefs, "reminderV2", None), "inReminder", None)
    if reminder is not None and not getattr(reminder, "enabled", False):
        reminder = None
    interval_minutes = interval_override_minutes or reminder_value_minutes(
        getattr(reminder, "value", None)
    )
    if last_feed is None or interval_minutes is None:
        return None

    event_time = last_feed + timedelta(minutes=interval_minutes)
    if event_time < now - timedelta(minutes=30):
        return None
    return Reminder(
        key=f"feed:{int(last_feed.timestamp())}:{interval_minutes}",
        kind="feed",
        event_time=event_time,
        announce_at=(
            last_feed + timedelta(minutes=announce_after_minutes)
            if announce_after_minutes is not None
            else event_time - timedelta(minutes=lead_minutes)
        ),
        message=f"距离{baby_name}下次吃奶还有{lead_minutes}分钟，可以开始准备了哦",
    )
