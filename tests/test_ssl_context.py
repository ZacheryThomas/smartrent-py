import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from smartrent.utils import Client


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise asyncio.CancelledError

    async def send(self, payload):
        self.sent.append(payload)


def make_client(ssl_context):
    client = object.__new__(Client)
    client._ssl_context = ssl_context
    client._token = "token"
    client._ws = None
    client._subscribed_devices = set()
    client._aiohttp_session = SimpleNamespace(closed=True)
    client._im_session_owner = False
    client._updater_task = None
    client._async_refresh_token = AsyncMock()
    client._async_fetch_subscribed_devices_status = AsyncMock()
    client._async_ws_joiner = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_ssl_context_passed_to_updater(monkeypatch):
    ssl_context = object()
    websocket = FakeWebSocket()
    connect_calls = []

    def connect(*args, **kwargs):
        connect_calls.append((args, kwargs))
        return websocket

    monkeypatch.setattr("smartrent.utils.websockets.connect", connect)
    client = make_client(ssl_context)

    with pytest.raises(asyncio.CancelledError):
        await client._async_update_state_via_ws()

    assert connect_calls[0][1]["ssl"] is ssl_context


@pytest.mark.asyncio
async def test_ssl_context_passed_to_command_connection(monkeypatch):
    ssl_context = object()
    websocket = FakeWebSocket()
    connect_calls = []

    def connect(*args, **kwargs):
        connect_calls.append((args, kwargs))
        return websocket

    monkeypatch.setattr("smartrent.utils.websockets.connect", connect)
    client = make_client(ssl_context)
    device = SimpleNamespace(_device_id=123, _name="Lock")

    await client._async_send_payload(device, "payload")

    assert connect_calls[0][1]["ssl"] is ssl_context
    assert websocket.sent == ["payload"]


@pytest.mark.asyncio
async def test_none_ssl_context_uses_websockets_secure_default_for_updater(monkeypatch):
    websocket = FakeWebSocket()
    connect_calls = []

    def connect(*args, **kwargs):
        connect_calls.append((args, kwargs))
        return websocket

    monkeypatch.setattr("smartrent.utils.websockets.connect", connect)
    client = make_client(None)

    with pytest.raises(asyncio.CancelledError):
        await client._async_update_state_via_ws()

    assert "ssl" not in connect_calls[0][1]


@pytest.mark.asyncio
async def test_none_ssl_context_uses_websockets_secure_default_for_command(monkeypatch):
    websocket = FakeWebSocket()
    connect_calls = []

    def connect(*args, **kwargs):
        connect_calls.append((args, kwargs))
        return websocket

    monkeypatch.setattr("smartrent.utils.websockets.connect", connect)
    client = make_client(None)
    device = SimpleNamespace(_device_id=123, _name="Lock")

    await client._async_send_payload(device, "payload")

    assert "ssl" not in connect_calls[0][1]
    assert websocket.sent == ["payload"]
