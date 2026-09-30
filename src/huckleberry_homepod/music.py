from __future__ import annotations

import asyncio
import errno
import ipaddress
import logging
import plistlib
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pyatv
from pyatv.conf import AppleTV, ManualService
from pyatv.const import Protocol
from pyatv.protocols.airplay.channels import EventChannel
from pyatv.protocols.raop.protocols import airplayv2

from .config import Config

LOGGER = logging.getLogger(__name__)

_PAUSE_COMMANDS = {"paus", "stop"}
_pause_listeners: dict[str, Callable[[], None]] = {}


class _RemoteCommandEventChannel(EventChannel):
    """Event channel that reports HomePod pause taps.

    pyatv acknowledges media remote commands from the receiver but otherwise
    ignores them, so a tap on the HomePod would not end the stream.
    """

    def handle_received(self) -> None:
        pending = self.buffer
        while pending:
            try:
                request, _, pending = self.parse_request(pending)
            except Exception:
                break
            if request is None:
                break
            self._dispatch(request.body)
        super().handle_received()

    def _dispatch(self, body: bytes | str) -> None:
        if not isinstance(body, bytes):
            return
        try:
            message = plistlib.loads(body)
        except Exception:
            return
        if (
            message.get("type") != "sendMediaRemoteCommand"
            or message.get("value") not in _PAUSE_COMMANDS
            or self.transport is None
        ):
            return
        listener = _pause_listeners.get(self.transport.get_extra_info("peername")[0])
        if listener is not None:
            listener()


airplayv2.EventChannel = _RemoteCommandEventChannel

# pyatv picks AirPlay 1 when these RAOP properties are missing, and HomePods
# accept an AirPlay 1 stream but stay silent.
HOMEPOD_RAOP_PROPERTIES = {
    "cn": "0,1,2,3",
    "et": "0,3,5",
    "ft": "0x4A7FCA00,0x3C354BD0",
    "md": "0,1,2",
    "sf": "0x80404",
    "tp": "UDP",
    "am": "AudioAccessory5,1",
}


class DirectMusicPlayer:
    """Stream one continuous, infinitely looped audio source to a HomePod."""

    def __init__(self, config: Config) -> None:
        self.config = config

    async def _connect(self) -> tuple[pyatv.interface.AppleTV, str]:
        loop = asyncio.get_running_loop()
        if self.config.music_homepod_host:
            device_config = AppleTV(
                ipaddress.ip_address(self.config.music_homepod_host),
                "Music HomePod",
            )
            device_config.add_service(
                ManualService(
                    self.config.music_homepod_id,
                    Protocol.RAOP,
                    7000,
                    properties=HOMEPOD_RAOP_PROPERTIES,
                )
            )
            device = await pyatv.connect(
                device_config,
                loop,
                protocol=Protocol.RAOP,
            )
            return device, self.config.music_homepod_host

        target_id = self.config.music_homepod_id.replace(":", "").lower()
        attempts = 6
        for attempt in range(1, attempts + 1):
            devices = await pyatv.scan(
                loop,
                timeout=8,
                protocol=Protocol.RAOP,
            )
            matching_devices = [
                device
                for device in devices
                if device.identifier
                and device.identifier.replace(":", "").lower() == target_id
            ]
            if matching_devices:
                device = await pyatv.connect(
                    matching_devices[0],
                    loop,
                    protocol=Protocol.RAOP,
                )
                return device, str(matching_devices[0].address)
            if attempt < attempts:
                LOGGER.warning(
                    "未发现音乐 HomePod，5 秒后重试（%s/%s）",
                    attempt,
                    attempts,
                )
                await asyncio.sleep(5)
        raise RuntimeError("找不到音乐 HomePod，请确认设备和 Mac 在同一网络")

    async def play_loop(self) -> None:
        music_file = self.config.music_file
        if music_file is None:
            return
        if not music_file.is_file():
            raise RuntimeError(f"找不到入睡音乐：{music_file}")
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            raise RuntimeError("找不到 ffmpeg，请先运行 `brew install ffmpeg`")
        if self.config.dry_run:
            LOGGER.info("[试运行] 将持续推流入睡音乐：%s", music_file)
            return

        attempts = 6
        for attempt in range(1, attempts + 1):
            try:
                await self._play_once(music_file, ffmpeg)
                return
            except OSError as error:
                if error.errno != errno.EHOSTUNREACH or attempt == attempts:
                    raise
                LOGGER.warning(
                    "音乐 HomePod 暂时无法连接，5 秒后重试推流（%s/%s）",
                    attempt,
                    attempts,
                )
                await asyncio.sleep(5)

    async def _play_once(self, music_file: Path, ffmpeg: str) -> None:
        device, address = await self._connect()
        process: subprocess.Popen[bytes] | None = None

        def on_pause() -> None:
            LOGGER.info("音乐 HomePod 被手动暂停")
            asyncio.ensure_future(device.remote_control.stop())

        _pause_listeners[address] = on_pause
        try:
            await device.audio.set_volume(self.config.music_volume)
            process = subprocess.Popen(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-stream_loop",
                    "-1",
                    "-i",
                    str(music_file),
                    "-vn",
                    "-codec:a",
                    "libmp3lame",
                    "-q:a",
                    "5",
                    "-f",
                    "mp3",
                    "pipe:1",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if process.stdout is None:
                raise RuntimeError("无法读取 ffmpeg 音频输出")
            await asyncio.sleep(0.5)
            if process.poll() is not None:
                detail = (
                    process.stderr.read().decode(errors="replace").strip()
                    if process.stderr is not None
                    else ""
                )
                raise RuntimeError(
                    f"ffmpeg 启动失败：{detail or f'exit code {process.returncode}'}"
                )

            LOGGER.info(
                "开始向音乐 HomePod 持续推流（音量 %.0f%%）：%s",
                self.config.music_volume,
                music_file,
            )
            await device.stream.stream_file(process.stdout)
            LOGGER.info("音乐 HomePod 已停止，本次入睡音乐结束")
        finally:
            _pause_listeners.pop(address, None)
            if process is not None:
                if process.stdout is not None:
                    process.stdout.close()
                if process.stderr is not None:
                    process.stderr.close()
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
            await asyncio.gather(*device.close())

    async def stop(self) -> None:
        device, _ = await self._connect()
        try:
            await device.remote_control.stop()
        finally:
            await asyncio.gather(*device.close())
