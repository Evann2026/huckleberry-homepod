from __future__ import annotations

import argparse
import asyncio
import logging
import sys

import pyatv
from pyatv.const import Protocol

from .app import ReminderService
from .config import Config, ConfigError
from .music import DirectMusicPlayer
from .notifier import HomePodNotifier


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Huckleberry HomePod 自动提醒")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("scan", help="查找局域网中的 HomePod")
    test = subparsers.add_parser("test-homepod", help="测试 HomePod 中文播报")
    test.add_argument("--message", default="HomePod 提醒测试成功。")
    subparsers.add_parser("test-music", help="测试 HomePod 持续音乐推流")
    subparsers.add_parser("stop-music", help="停止 HomePod 音乐推流")
    subparsers.add_parser("inspect", help="显示当前预测，不进行播报")
    subparsers.add_parser("once", help="同步一次并播报到期提醒")
    subparsers.add_parser("run", help="持续运行提醒服务")
    return parser


async def _scan() -> int:
    devices = await pyatv.scan(
        asyncio.get_running_loop(),
        timeout=8,
        protocol=Protocol.RAOP,
    )
    if not devices:
        print("未发现 AirPlay 音箱。请检查同一网络和 macOS 本地网络权限。")
        return 1
    for device in devices:
        print(f"{device.name}\n  Identifier: {device.identifier}\n  地址: {device.address}")
    return 0


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    args = _parser().parse_args()
    try:
        if args.command == "scan":
            raise SystemExit(asyncio.run(_scan()))
        if args.command == "test-homepod":
            asyncio.run(
                HomePodNotifier(Config.load(require_huckleberry=False)).announce(args.message)
            )
            return
        if args.command in {"test-music", "stop-music"}:
            player = DirectMusicPlayer(Config.load(require_huckleberry=False))
            if args.command == "test-music":
                asyncio.run(player.play_loop())
            else:
                asyncio.run(player.stop())
            return

        service = ReminderService(Config.load())
        if args.command == "inspect":
            asyncio.run(service.once(show=True, announce=False))
        elif args.command == "once":
            asyncio.run(service.once())
        else:
            asyncio.run(service.run())
    except ConfigError as error:
        print(error, file=sys.stderr)
        raise SystemExit(2) from error
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
