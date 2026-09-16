from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import aiohttp
from huckleberry_api import HuckleberryAPI

from .config import Config
from .notifier import HomePodNotifier
from .predictions import Reminder, feed_reminder, sleep_reminders

LOGGER = logging.getLogger(__name__)


def is_quiet_time(moment: datetime, start_hour: int, end_hour: int) -> bool:
    if start_hour == end_hour:
        return False
    if start_hour < end_hour:
        return start_hour <= moment.hour < end_hour
    return moment.hour >= start_hour or moment.hour < end_hour


class ReminderService:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.notifier = HomePodNotifier(config)
        self.sent = self._load_state(config.state_file)

    @staticmethod
    def _load_state(path: Path) -> set[str]:
        try:
            data = json.loads(path.read_text())
            return set(data.get("sent", []))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return set()

    def _save_state(self) -> None:
        self.config.state_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.config.state_file.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"sent": sorted(self.sent)[-200:]}, ensure_ascii=False)
        )
        temporary.replace(self.config.state_file)

    async def _connect(self) -> tuple[aiohttp.ClientSession, HuckleberryAPI, str]:
        session = aiohttp.ClientSession()
        try:
            api = HuckleberryAPI(
                email=self.config.email,
                password=self.config.password,
                timezone=self.config.timezone,
                websession=session,
            )
            await api.authenticate()
            user = await api.get_user()
            child_id = self.config.child_id
            if child_id is None:
                if not user.childList:
                    raise RuntimeError("Huckleberry 账户中没有儿童资料")
                child_id = user.childList[0].cid
            return session, api, child_id
        except Exception:
            await session.close()
            raise

    async def fetch_reminders(
        self, api: HuckleberryAPI, child_id: str
    ) -> list[Reminder]:
        now = datetime.now(ZoneInfo(self.config.timezone))
        child, feed = await asyncio.gather(
            api.get_child(child_id),
            api.get_nursing(child_id),
        )
        if child is None:
            raise RuntimeError(f"找不到儿童资料：{child_id}")

        reminders = sleep_reminders(
            child.sweetspot.sweetSpotTimes if child.sweetspot else None,
            selected_nap_day=self.config.sleep_nap_schedule,
            now=now,
            timezone=self.config.timezone,
            lead_minutes=self.config.sleep_lead_minutes,
            announce_lead_minutes=self.config.sleep_announce_lead_minutes,
            baby_name=self.config.baby_name,
        )
        feeding = feed_reminder(
            feed,
            now=now,
            timezone=self.config.timezone,
            lead_minutes=self.config.feed_lead_minutes,
            announce_after_minutes=self.config.feed_announce_after_minutes,
            interval_override_minutes=self.config.feed_interval_minutes,
            baby_name=self.config.baby_name,
        )
        if feeding is not None:
            reminders.append(feeding)
        return sorted(reminders, key=lambda item: item.event_time)

    async def announce_due(self, reminders: list[Reminder]) -> None:
        now = datetime.now(ZoneInfo(self.config.timezone))
        if is_quiet_time(
            now,
            self.config.quiet_start_hour,
            self.config.quiet_end_hour,
        ):
            return

        for reminder in reminders:
            if is_quiet_time(
                reminder.announce_at,
                self.config.quiet_start_hour,
                self.config.quiet_end_hour,
            ):
                continue
            is_due = reminder.announce_at <= now <= reminder.event_time + timedelta(minutes=5)
            if not is_due or reminder.key in self.sent:
                continue
            await self.notifier.announce(reminder.message)
            self.sent.add(reminder.key)
            self._save_state()
            LOGGER.info(
                "已播报 %s 提醒（预计时间 %s）",
                reminder.kind,
                reminder.event_time.strftime("%H:%M"),
            )

    async def once(self, *, show: bool = False, announce: bool = True) -> None:
        session, api, child_id = await self._connect()
        try:
            reminders = await self.fetch_reminders(api, child_id)
            if show:
                self._print_reminders(reminders)
            if announce:
                await self.announce_due(reminders)
        finally:
            await api.stop_all_listeners()
            await session.close()

    async def run(self) -> None:
        LOGGER.info("提醒服务已启动")
        while True:
            session: aiohttp.ClientSession | None = None
            api: HuckleberryAPI | None = None
            try:
                session, api, child_id = await self._connect()
                while True:
                    reminders = await self.fetch_reminders(api, child_id)
                    await self.announce_due(reminders)
                    await asyncio.sleep(self.config.poll_seconds)
            except Exception:
                LOGGER.exception("同步连接失败，将在下个周期重新连接")
            finally:
                if api is not None:
                    await api.stop_all_listeners()
                if session is not None:
                    await session.close()
            await asyncio.sleep(self.config.poll_seconds)

    @staticmethod
    def _print_reminders(reminders: list[Reminder]) -> None:
        if not reminders:
            print("当前没有可用的睡眠或吃奶提醒。")
            return
        for reminder in reminders:
            print(
                f"{reminder.kind:5} 预计 {reminder.event_time:%Y-%m-%d %H:%M} "
                f"播报 {reminder.announce_at:%H:%M}"
            )
