from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(ValueError):
    pass


def _optional_int(name: str) -> int | None:
    value = os.getenv(name, "").strip()
    return int(value) if value else None


def _percentage(name: str, default: str) -> float:
    value = float(os.getenv(name, default))
    if not 0 <= value <= 100:
        raise ConfigError(f"{name} 必须在 0 到 100 之间")
    return value


def _clock_time(name: str, default: str) -> time:
    try:
        return datetime.strptime(os.getenv(name, default), "%H:%M").time()
    except ValueError as error:
        raise ConfigError(f"{name} 必须使用 HH:MM 格式") from error


@dataclass(frozen=True)
class Config:
    email: str
    password: str
    baby_name: str
    timezone: str
    homepod_id: str
    homepod_volume: float
    music_homepod_id: str
    music_homepod_host: str | None
    music_file: Path | None
    music_volume: float
    child_id: str | None
    sleep_lead_minutes: int
    sleep_announce_lead_minutes: int
    sleep_nap_schedule: int
    feed_lead_minutes: int
    feed_announce_after_minutes: int
    feed_interval_minutes: int | None
    poll_seconds: int
    quiet_start_time: time
    quiet_end_time: time
    state_file: Path
    dry_run: bool

    @classmethod
    def load(cls, *, require_huckleberry: bool = True) -> Config:
        load_dotenv()
        email = os.getenv("HUCKLEBERRY_EMAIL", "").strip()
        password = os.getenv("HUCKLEBERRY_PASSWORD", "")
        homepod_id = os.getenv("HOMEPOD_ID", "").strip()
        music_file_value = os.getenv("MUSIC_FILE", "").strip()

        missing = []
        if require_huckleberry:
            if not email:
                missing.append("HUCKLEBERRY_EMAIL")
            if not password:
                missing.append("HUCKLEBERRY_PASSWORD")
        if not homepod_id and os.getenv("DRY_RUN", "0") != "1":
            missing.append("HOMEPOD_ID")
        if missing:
            raise ConfigError(f"请在 .env 中设置：{', '.join(missing)}")

        return cls(
            email=email,
            password=password,
            baby_name=os.getenv("BABY_NAME", "宝宝").strip() or "宝宝",
            timezone=os.getenv("TIMEZONE", "America/Los_Angeles"),
            homepod_id=homepod_id,
            homepod_volume=_percentage("HOMEPOD_VOLUME", "70"),
            music_homepod_id=(
                os.getenv("MUSIC_HOMEPOD_ID", "").strip() or homepod_id
            ),
            music_homepod_host=(
                os.getenv("MUSIC_HOMEPOD_HOST", "").strip() or None
            ),
            music_file=Path(music_file_value).expanduser() if music_file_value else None,
            music_volume=_percentage("MUSIC_VOLUME", "20"),
            child_id=os.getenv("HUCKLEBERRY_CHILD_ID") or None,
            sleep_lead_minutes=int(os.getenv("SLEEP_LEAD_MINUTES", "15")),
            sleep_announce_lead_minutes=int(
                os.getenv("SLEEP_ANNOUNCE_LEAD_MINUTES", "16")
            ),
            sleep_nap_schedule=int(os.getenv("SLEEP_NAP_SCHEDULE", "3")),
            feed_lead_minutes=int(os.getenv("FEED_LEAD_MINUTES", "30")),
            feed_announce_after_minutes=int(
                os.getenv("FEED_ANNOUNCE_AFTER_MINUTES", "179")
            ),
            feed_interval_minutes=_optional_int("FEED_INTERVAL_MINUTES") or 210,
            poll_seconds=max(15, int(os.getenv("POLL_SECONDS", "60"))),
            quiet_start_time=_clock_time("QUIET_START_TIME", "19:30"),
            quiet_end_time=_clock_time("QUIET_END_TIME", "08:00"),
            state_file=Path(os.getenv("STATE_FILE", "~/.huckleberry-homepod-state.json")).expanduser(),
            dry_run=os.getenv("DRY_RUN", "0") == "1",
        )
