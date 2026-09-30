import plistlib

from huckleberry_homepod import music


class FakeTransport:
    def __init__(self, address: str) -> None:
        self.address = address

    def get_extra_info(self, name: str):
        assert name == "peername"
        return (self.address, 7000)


def _command(value: str) -> bytes:
    body = plistlib.dumps(
        {"type": "sendMediaRemoteCommand", "value": value},
        fmt=plistlib.FMT_BINARY,
    )
    return (
        b"POST /command RTSP/1.0\r\n"
        b"CSeq: 1\r\n"
        b"Content-Type: application/x-apple-binary-plist\r\n"
        + f"Content-Length: {len(body)}\r\n\r\n".encode()
        + body
    )


def _channel(address: str, data: bytes):
    channel = music._RemoteCommandEventChannel.__new__(
        music._RemoteCommandEventChannel
    )
    channel.buffer = data
    channel.transport = FakeTransport(address)
    channel.send = lambda _data: None
    return channel


def test_homepod_pause_tap_notifies_only_music_homepod() -> None:
    calls: list[str] = []
    music._pause_listeners["10.0.0.69"] = lambda: calls.append("music")
    try:
        _channel("10.0.0.69", _command("play")).handle_received()
        assert calls == []

        _channel("10.0.0.81", _command("paus")).handle_received()
        assert calls == []

        _channel("10.0.0.69", _command("paus")).handle_received()
        assert calls == ["music"]
    finally:
        music._pause_listeners.clear()
