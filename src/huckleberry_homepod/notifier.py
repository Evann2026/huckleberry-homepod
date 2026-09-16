from __future__ import annotations

import asyncio
import logging
import subprocess
import tempfile
from pathlib import Path

import pyatv
from pyatv.const import Protocol

from .config import Config

LOGGER = logging.getLogger(__name__)


class HomePodNotifier:
    def __init__(self, config: Config) -> None:
        self.config = config

    async def announce(self, message: str) -> None:
        if self.config.dry_run:
            LOGGER.info("[试运行] %s", message)
            return

        with tempfile.TemporaryDirectory(prefix="hb-homepod-") as temp_dir:
            source_audio = Path(temp_dir) / "announcement.aiff"
            audio = Path(temp_dir) / "announcement.wav"
            subprocess.run(
                ["say", "-v", "Tingting", "-o", str(source_audio), message],
                check=True,
                timeout=30,
            )
            subprocess.run(
                [
                    "afconvert",
                    "-f",
                    "WAVE",
                    "-d",
                    "LEI16",
                    str(source_audio),
                    str(audio),
                ],
                check=True,
                timeout=30,
            )
            loop = asyncio.get_running_loop()
            devices = await pyatv.scan(
                loop,
                timeout=8,
                identifier=self.config.homepod_id,
                protocol=Protocol.RAOP,
            )
            if not devices:
                raise RuntimeError("找不到配置的 HomePod，请确认设备和 Mac 在同一网络")

            device = await pyatv.connect(devices[0], loop, protocol=Protocol.RAOP)
            try:
                await device.audio.set_volume(self.config.homepod_volume)
                await device.stream.stream_file(str(audio))
            finally:
                await asyncio.gather(*device.close())
