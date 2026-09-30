import asyncio
from datetime import datetime, time, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from huckleberry_homepod.app import ReminderService
from huckleberry_homepod.predictions import Reminder


class FakeNotifier:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def announce(self, message: str) -> None:
        self.messages.append(message)


class FakeMusicPlayer:
    def __init__(self) -> None:
        self.play_count = 0

    async def play_loop(self) -> None:
        self.play_count += 1


def test_music_starts_only_after_sleep_reminder() -> None:
    async def run() -> None:
        service = ReminderService.__new__(ReminderService)
        service.config = SimpleNamespace(
            timezone="UTC",
            quiet_start_time=time(0),
            quiet_end_time=time(0),
        )
        service.notifier = FakeNotifier()
        service.music_player = FakeMusicPlayer()
        service.music_task = None
        service.sent = set()
        service._save_state = lambda: None
        now = datetime.now(ZoneInfo("UTC"))

        # Feeding announcements do not control playback on the separate music HomePod.
        await service.announce_due(
            [
                Reminder(
                    key="feed:1",
                    kind="feed",
                    event_time=now + timedelta(minutes=30),
                    announce_at=now - timedelta(seconds=1),
                    message="feed",
                )
            ]
        )
        assert service.music_player.play_count == 0

        # A sleep reminder starts one continuous looped RAOP stream.
        await service.announce_due(
            [
                Reminder(
                    key="sleep:1",
                    kind="sleep",
                    event_time=now + timedelta(minutes=15),
                    announce_at=now - timedelta(seconds=1),
                    message="sleep",
                )
            ]
        )
        await asyncio.sleep(0)
        assert service.music_player.play_count == 1

    asyncio.run(run())
