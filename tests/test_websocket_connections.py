"""Tests for SmartRent WebSocket connection settings and lifecycle."""

import asyncio
from contextlib import suppress
import json
import time
import unittest
from unittest.mock import patch

from websockets.asyncio.server import serve

from smartrent.utils import (
    SMARTRENT_WEBSOCKET_MAX_QUEUE,
    SMARTRENT_WEBSOCKET_MAX_SIZE,
    Client,
)


class FakeSession:
    """Minimal externally owned aiohttp session replacement."""

    closed = False


class FakeDevice:
    """Minimal SmartRent device for command tests."""

    _device_id = 123
    _name = "Test Device"


class UpdatingDevice(FakeDevice):
    """Device test double that records updates from a real WebSocket server."""

    def __init__(self):
        self.updates = []
        self.received_two_updates = asyncio.Event()

    async def _update(self, event):
        self.updates.append(event)
        if len(self.updates) == 2:
            self.received_two_updates.set()


class FakeWebSocket:
    """WebSocket test double that can fail while receiving."""

    def __init__(self, receive_error=None):
        self.receive_error = receive_error
        self.sent = []

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.receive_error:
            raise self.receive_error
        raise StopAsyncIteration

    async def send(self, payload):
        self.sent.append(payload)


class FakeConnectContext:
    """Async context manager returned by websockets.connect."""

    def __init__(self, websocket):
        self.websocket = websocket
        self.exited = False

    async def __aenter__(self):
        return self.websocket

    async def __aexit__(self, exc_type, exc, traceback):
        self.exited = True


class WebSocketConnectionTests(unittest.TestCase):
    """Verify all SmartRent WebSocket connections remain bounded."""

    def make_client(self):
        client = Client("test@example.invalid", "not-a-password", FakeSession())
        client._token = "test-token"
        client._token_exp_time = int(time.time()) + 3600
        return client

    def assert_bounded_connection(self, kwargs):
        self.assertEqual(kwargs["max_queue"], SMARTRENT_WEBSOCKET_MAX_QUEUE)
        self.assertIsNotNone(kwargs["max_queue"])
        self.assertEqual(kwargs["max_size"], SMARTRENT_WEBSOCKET_MAX_SIZE)
        self.assertIsNotNone(kwargs["max_size"])

    def test_persistent_connection_is_bounded_and_reconnects(self):
        client = self.make_client()
        connect_calls = []
        first_context = FakeConnectContext(
            FakeWebSocket(receive_error=ConnectionResetError("test disconnect"))
        )

        def fake_connect(uri, **kwargs):
            connect_calls.append((uri, kwargs))
            if len(connect_calls) == 1:
                return first_context
            raise asyncio.CancelledError

        async def run_test():
            with patch("smartrent.utils.websockets.connect", side_effect=fake_connect):
                await client._async_update_state_via_ws()

        with self.assertRaises(asyncio.CancelledError):
            asyncio.run(run_test())

        self.assertEqual(len(connect_calls), 2)
        self.assertTrue(first_context.exited)

        uri, kwargs = connect_calls[0]
        self.assertIn("test-token", uri)
        self.assertEqual(
            kwargs["additional_headers"], {"Authorization": "Bearer test-token"}
        )
        self.assertEqual(kwargs["ping_interval"], 15)
        self.assertEqual(kwargs["ping_timeout"], 10)
        self.assertEqual(kwargs["close_timeout"], 5)
        self.assert_bounded_connection(kwargs)

    def test_command_connection_is_explicitly_bounded(self):
        client = self.make_client()
        websocket = FakeWebSocket()
        context = FakeConnectContext(websocket)
        connect_calls = []

        def fake_connect(uri, **kwargs):
            connect_calls.append((uri, kwargs))
            return context

        async def run_test():
            with patch("smartrent.utils.websockets.connect", side_effect=fake_connect):
                await client._async_send_payload(FakeDevice(), "test-payload")

        asyncio.run(run_test())

        self.assertEqual(len(connect_calls), 1)
        self.assertTrue(context.exited)
        self.assertEqual(len(websocket.sent), 2)
        self.assertEqual(websocket.sent[-1], "test-payload")

        uri, kwargs = connect_calls[0]
        self.assertIn("test-token", uri)
        self.assertEqual(
            kwargs["additional_headers"], {"Authorization": "Bearer test-token"}
        )
        self.assertEqual(kwargs["ping_interval"], 15)
        self.assertEqual(kwargs["ping_timeout"], 10)
        self.assertEqual(kwargs["close_timeout"], 5)
        self.assert_bounded_connection(kwargs)

    def test_real_websocket_updates_resume_after_reconnect(self):
        async def run_test():
            device = UpdatingDevice()
            client = self.make_client()
            client._subscribed_devices.add(device)
            connection_count = 0
            active_connections = set()

            async def handler(websocket):
                nonlocal connection_count
                connection_count += 1
                active_connections.add(websocket)
                try:
                    await websocket.recv()
                    await websocket.send(
                        json.dumps(
                            [
                                "null",
                                "null",
                                "devices:123",
                                "event",
                                {
                                    "type": "Lock",
                                    "name": "locked",
                                    "last_read_state": "true",
                                },
                            ]
                        )
                    )
                    if connection_count == 1:
                        await websocket.close()
                    else:
                        await websocket.wait_closed()
                finally:
                    active_connections.discard(websocket)

            async with serve(handler, "127.0.0.1", 0) as server:
                port = server.sockets[0].getsockname()[1]
                uri = f"ws://127.0.0.1:{port}/socket?token={{}}"
                with patch("smartrent.utils.SMARTRENT_WEBSOCKET_URI", uri):
                    updater = asyncio.create_task(client._async_update_state_via_ws())
                    await asyncio.wait_for(device.received_two_updates.wait(), 5)
                    updater.cancel()
                    with suppress(asyncio.CancelledError):
                        await updater

                await asyncio.sleep(0)

            self.assertGreaterEqual(connection_count, 2)
            self.assertEqual(len(device.updates), 2)
            self.assertFalse(active_connections)

        asyncio.run(run_test())

    def test_canceling_updater_cancels_fetch_and_websocket_tasks(self):
        async def run_test():
            client = self.make_client()
            fetch_started = asyncio.Event()
            websocket_started = asyncio.Event()
            fetch_stopped = asyncio.Event()
            websocket_stopped = asyncio.Event()

            async def wait_until_cancelled(started, stopped):
                started.set()
                try:
                    await asyncio.Future()
                finally:
                    stopped.set()

            with patch.object(
                client,
                "_async_update_state_via_fetch",
                new=lambda: wait_until_cancelled(fetch_started, fetch_stopped),
            ), patch.object(
                client,
                "_async_update_state_via_ws",
                new=lambda: wait_until_cancelled(websocket_started, websocket_stopped),
            ):
                updater = asyncio.create_task(client._async_update_state())
                await asyncio.gather(fetch_started.wait(), websocket_started.wait())
                updater.cancel()
                with suppress(asyncio.CancelledError):
                    await updater

            self.assertTrue(fetch_stopped.is_set())
            self.assertTrue(websocket_stopped.is_set())

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
