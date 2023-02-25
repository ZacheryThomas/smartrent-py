import asyncio
import json
import logging
import math
import time
import traceback
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

import aiohttp
import websockets

if TYPE_CHECKING:
    from smartrent.device import Device

_LOGGER = logging.getLogger(__name__)

SMARTRENT_FETCH_INTERVAL_SECONDS = 600

SMARTRENT_BASE_URI = "https://control.smartrent.com/api/v2/"
SMARTRENT_SESSIONS_URI = SMARTRENT_BASE_URI + "sessions"
SMARTRENT_TOKENS_URI = SMARTRENT_BASE_URI + "tokens"
SMARTRENT_HUBS_URI = SMARTRENT_BASE_URI + "hubs"
SMARTRENT_HUBS_ID_URI = SMARTRENT_BASE_URI + "hubs/{}/devices"
SMARTRENT_DEVICE_URI = SMARTRENT_BASE_URI + "devices/{}"

SMARTRENT_WEBSOCKET_URI = (
    "wss://control.smartrent.com/socket/websocket?token={}&vsn=2.0.0"
)
JOINER_PAYLOAD = '["null", "null", "devices:{device_id}", "phx_join", {{}}]'
COMMAND_PAYLOAD = (
    '["null", "null", "devices:{device_id}", "update_attributes", '
    '{{"device_id": {device_id}, '
    '"attributes": [{{"name": "{attribute_name}", "value": "{value}"}}]}}]'
)


class SmartRentError(Exception):
    """
    Base error for SmartRent
    """


class InvalidAuthError(SmartRentError):
    """
    Error related to invalid auth
    """


class Client:
    """
    Represents Client for SmartRent http and websocket api.
    Usually shared between multiple devices for best performance.

    ``email`` is the email address for your SmartRent account

    ``password`` you know what it is

    ``aiohttp_session`` (optional) uses the aiohttp_session that is passed in

    ``tfa_token`` (optional) tfa token to pass in for login
    """

    def __init__(
        self,
        email: str,
        password: str,
        aiohttp_session: aiohttp.ClientSession = None,
        tfa_token: str = None,
    ):
        self._email = email
        self._password = password

        self._im_session_owner = not bool(aiohttp_session)
        self._aiohttp_session = (
            aiohttp_session if aiohttp_session else aiohttp.ClientSession()
        )
        self._token = None
        self._refresh_token = None
        self._token_exp_time = None
        self._tfa_token = tfa_token

        self._subscribed_devices: Set["Device"] = set()
        self._updater_task: Optional[asyncio.Task[Any]] = None
        self._ws = None

        self._refresh_token_lock: Optional[asyncio.Lock] = None

    def __del__(self):
        """
        Handles delete of aiohttp session if class is tasked with it
        """
        if not self._aiohttp_session.closed and self._im_session_owner:
            _LOGGER.debug(
                "%s: closing aiohttp session %s", str(self), self._aiohttp_session
            )

            try:
                _LOGGER.debug("Finding running event loop")
                current_loop = asyncio.get_running_loop()
                current_loop.create_task(self._aiohttp_session.close())

            except RuntimeError:
                _LOGGER.debug("Making new event loop")
                new_loop = asyncio.new_event_loop()
                new_loop.run_until_complete(self._aiohttp_session.close())

        if self._updater_task:
            _LOGGER.info("Stopping updater task")
            self._updater_task.cancel()
            self._ws = None

    async def async_get_devices_data(self) -> List[dict]:
        """
        Gets list of device dictionaries from SmartRent's api.
        Also handles retry if token is bad
        """
        if not self._token:
            await self._async_refresh_token()

        try:
            res = await self._async_get_devices_data()
        except InvalidAuthError:
            _LOGGER.warning("InvalidAuth detected. Trying again with updated token...")
            await self._async_refresh_token()

            res = await self._async_get_devices_data()

        return res

    async def _async_get_devices_data(self) -> List[dict]:
        """
        Gets list of device dictionaries from SmartRent's api
        """

        hubs_resp = await self._aiohttp_session.get(
            SMARTRENT_HUBS_URI, headers={"authorization": f"Bearer {self._token}"}
        )
        hubs = await hubs_resp.json()

        if not hubs_resp.ok:
            if hubs.get("errors", [{}])[0].get("code") == "unauthorized":
                raise InvalidAuthError(hubs.get("errors"))

        devices_list = []
        for hub in hubs:
            devices_resp = await self._aiohttp_session.get(
                SMARTRENT_HUBS_ID_URI.format(hub["id"]),
                headers={"authorization": f"Bearer {self._token}"},
            )
            devices = await devices_resp.json()

            for device in devices:
                _LOGGER.info("Found %s: %s", device["id"], device["name"])
                devices_list.append(device)

        return devices_list

    async def async_get_device_data(self, id: int) -> Dict[str, Any]:
        """
        Gets device dictionary from SmartRent's api.
        Also handles retry if token is bad
        """
        if not self._token:
            await self._async_refresh_token()

        try:
            res = await self._async_get_device_data(id)
        except InvalidAuthError:
            _LOGGER.warning("InvalidAuth detected. Trying again with updated token...")
            await self._async_refresh_token()

            res = await self._async_get_device_data(id)

        return res

    async def _async_get_device_data(self, id: int) -> Dict[str, Any]:
        """
        Gets list of device dictionary from SmartRent's api
        """

        device_resp = await self._aiohttp_session.get(
            SMARTRENT_DEVICE_URI.format(id),
            headers={"authorization": f"Bearer {self._token}"},
        )
        device_dict = await device_resp.json()

        if not device_resp.ok:
            if device_dict.get("errors", [{}])[0].get("code") == "unauthorized":
                raise InvalidAuthError(device_dict.get("errors"))

        return device_dict

    async def _async_refresh_token(self) -> None:
        """
        Refreshes API token from SmartRent
        """
        response = {}

        if not self._refresh_token_lock:
            self._refresh_token_lock = asyncio.Lock()

        if self._refresh_token_lock.locked():
            # Wait to have lock, then release it
            # since other thread already updated the token
            await self._refresh_token_lock.acquire()
            self._refresh_token_lock.release()
            return

        # Check to make sure token is expired before trying to refresh
        if self._token_exp_time:
            if self._token_exp_time > (math.ceil(time.time()) + 60):
                _LOGGER.info("Token not expired. Not refreshing.")
                return

        async with self._refresh_token_lock:
            if self._refresh_token:
                response = await self._async_refresh_tokens_via_refresh_token()

                # if refresh token has an error, default to email
                if response.get("errors"):
                    codes = [err["code"] for err in response.get("errors")]
                    if "unauthorized" in codes:
                        _LOGGER.warning(
                            "Refreshing with refresh_token failed with %s. "
                            "Trying with email and pass instead.",
                            response["errors"],
                        )
                        response = await self._async_refresh_tokens_via_email()
            else:
                response = await self._async_refresh_tokens_via_email()

                tfa_api_token = response.get("tfa_api_token")
                if tfa_api_token:
                    tfa_token = self._tfa_token or input("Enter in your 2fa token: ")
                    response = await self._async_refresh_tokens_via_tfa(
                        tfa_api_token, tfa_token
                    )

            if not response.get("errors"):
                # sometimes response needs to be extracted from "data"
                # https://github.com/ZacheryThomas/homeassistant-smartrent/issues/15
                response = response.get("data") or response

                self._token = response["access_token"]
                self._refresh_token = response["refresh_token"]
                self._token_exp_time = response["expires"]
                _LOGGER.info("Tokens refreshed!")
            else:
                raise InvalidAuthError(
                    "Token not retrieved! "
                    f'Loggin probably not successful: {response["errors"]}'
                )

    async def _async_refresh_tokens_via_email(self) -> dict:
        """
        Calls api endpoint to get initial tokens with email and password
        """
        _LOGGER.info("Refreshing tokens with email")
        data = {"email": self._email, "password": self._password}
        resp = await self._aiohttp_session.post(SMARTRENT_SESSIONS_URI, json=data)
        return await resp.json()

    async def _async_refresh_tokens_via_tfa(
        self, tfa_api_token: str, tfa_token: str
    ) -> dict:
        """
        Calls api endpoint to get tokens via a tfa api token and a tfa token
        """
        _LOGGER.info("Refreshing tokens with tfa support")
        data = {"tfa_api_token": tfa_api_token, "token": tfa_token}
        resp = await self._aiohttp_session.post(SMARTRENT_SESSIONS_URI, json=data)
        return await resp.json()

    async def _async_refresh_tokens_via_refresh_token(self) -> dict:
        """
        Calls api endpoint to get tokens given a refresh token
        """
        _LOGGER.info("Refreshing tokens with refresh token")
        headers = {"authorization-x-refresh": self._refresh_token}
        resp = await self._aiohttp_session.post(SMARTRENT_TOKENS_URI, headers=headers)
        return await resp.json()

    def _subscribe_device_to_updater(self, device: "Device"):
        """
        Subscribes device to recieve updates
        """
        self._subscribed_devices.add(device)

        if not self._updater_task:
            _LOGGER.info("Starting updater task")
            self._updater_task = asyncio.create_task(self._async_update_state())

        elif self._updater_task:
            if self._updater_task.cancelled():
                _LOGGER.info(
                    "Updater task was previously canceled. Starting updater task again."
                )
                self._updater_task = asyncio.create_task(self._async_update_state())

        if self._ws:
            asyncio.create_task(self._async_ws_joiner(self._ws, device))

    def _unsubscribe_device_to_updater(self, device: "Device"):
        """
        Unsubscribes device to recieve updates
        """
        try:
            self._subscribed_devices.remove(device)
        except KeyError:
            pass

        if self._updater_task:
            if (
                not self._updater_task.cancelled()
                and len(self._subscribed_devices) == 0
            ):
                _LOGGER.info("Device list empty. Stopping updater task for now.")
                self._updater_task.cancel()
                self._ws = None

    async def _async_fetch_subscribed_devices_status(self):
        """
        Calls ``_async_fetch_state`` for all subscribed devices
        """
        _LOGGER.info("Fetching current status for all devices...")
        await asyncio.gather(
            *[device._async_fetch_state() for device in self._subscribed_devices]
        )
        _LOGGER.info("Done fetching data!")

    async def _async_ws_joiner(self, ws, device: "Device"):
        """
        Joins ``Device`` to websocket
        """
        joiner = JOINER_PAYLOAD.format(device_id=device._device_id)
        _LOGGER.info(
            "Joining topic for %s:%s ...",
            device._name,
            device._device_id,
        )
        await ws.send(joiner)

    async def _async_ws_join_devices(self, ws, devices: List["Device"]):
        """
        Takes list of ``Device`` and joins them to websocket
        """
        _LOGGER.info("Joining devices to websocket conn...")
        await asyncio.gather(*[self._async_ws_joiner(ws, device) for device in devices])
        _LOGGER.info("Done Joining devices!")

    async def _async_update_state(self):
        """
        Responsible for handling automatic updating of device info
        """
        fetch = asyncio.create_task(self._async_update_state_via_fetch())
        ws = asyncio.create_task(self._async_update_state_via_ws())

        await asyncio.gather(fetch, ws)

    async def _async_update_state_via_fetch(self):
        """
        Connects to SmartRent rest api every
        ``SMARTRENT_FETCH_INTERVAL_SECONDS`` seconds for updates.
        To be ran in the background.
        Used to get ``online`` and ``battery`` information
        since those are not passed in through websockets events.

        Calls ``_async_fetch_state`` method for each subscribed device
        """
        while True:
            try:
                await self._async_fetch_subscribed_devices_status()
                await asyncio.sleep(SMARTRENT_FETCH_INTERVAL_SECONDS)

            except Exception as exc:
                _LOGGER.warning(
                    "Exception occured! %s %s", type(exc).__name__, type(exc)
                )
                _LOGGER.warning(traceback.format_exc())

                _LOGGER.warning(
                    "Retrying fetches in %s seconds...",
                    SMARTRENT_FETCH_INTERVAL_SECONDS,
                )

                await asyncio.sleep(SMARTRENT_FETCH_INTERVAL_SECONDS)

    async def _async_update_state_via_ws(self):
        """
        Connects to SmartRent websocket and listens for updates.
        To be ran in the background.

        Calls ``_update`` method for each device when event is found
        """

        retries = 0
        while True:
            try:
                self._ws = None

                _LOGGER.info("Getting new token")
                await self._async_refresh_token()
                token = self._token

                # If coming off of a retry:
                # Update all devices with newest data from regular api
                # we may have missed some stats if websocket was down
                if retries:
                    await self._async_fetch_subscribed_devices_status()

                uri = SMARTRENT_WEBSOCKET_URI.format(token)

                _LOGGER.info("Connecting to Websocket...")
                async with websockets.connect(uri) as websocket:
                    # if we connect sucessfully at least one time, reset retries to 0
                    retries = 0
                    self._ws = websocket

                    # Join all devices to websocket connection
                    await self._async_ws_join_devices(
                        websocket, self._subscribed_devices
                    )

                    # iterator to recieve messages from websocket
                    async for message in websocket:
                        message_list = json.loads(f"{message}")
                        formatted_resp = message_list[4]
                        device_id = message_list[2].split(":")[-1]

                        event_type = formatted_resp.get("type", "")
                        event_name = formatted_resp.get("name", "")
                        event_last_read_state = formatted_resp.get(
                            "last_read_state", ""
                        )

                        if event_type:
                            event = (
                                f"{event_type:<15} -> "
                                f"{event_name:<15} -> "
                                f"{event_last_read_state:<20}"
                            )
                            _LOGGER.info(event)

                            for device in self._subscribed_devices:
                                if device._device_id == int(device_id):
                                    await device._update(formatted_resp)
                        else:
                            _LOGGER.info(str(message))

            except Exception as exc:
                _LOGGER.warning(
                    "Exception occured! %s %s", type(exc).__name__, type(exc)
                )
                _LOGGER.warning(traceback.format_exc())

                # set websocket to None
                self._ws = None

                wait_time = 1.25**retries
                wait_time = wait_time if wait_time < 300 else 300
                _LOGGER.warning("Retrying websocket in %s seconds...", wait_time)

                await asyncio.sleep(wait_time)

                retries += 1

    async def _async_send_command(
        self, device: "Device", attribute_name: str, value: str
    ):
        """
        Sends command to SmartRent websocket

        ``attribute_name`` string of attribute to change

        ``value`` value for that attribute to be changed to
        """
        payload = COMMAND_PAYLOAD.format(
            attribute_name=attribute_name, value=value, device_id=device._device_id
        )
        try:
            await self._async_send_payload(device, payload)
        except websockets.exceptions.InvalidStatusCode as exc:  # type: ignore
            _LOGGER.debug(
                'Possible issue during send_payload: "%s" '
                "Refreshing token and retrying",
                exc,
            )

            # update token once
            await self._async_refresh_token()

            await self._async_send_payload(device, payload)

    async def _async_send_payload(self, device: "Device", payload: str):
        """
        Sends payload to SmartRent websocket

        ``device`` Device object

        ``payload`` string of device attributes

        Throws ``websockets.exceptions.InvalidStatusCode`` upon bad websocket event
        """
        _LOGGER.info("sending payload %s", payload)

        uri = SMARTRENT_WEBSOCKET_URI.format(self._token)

        async with websockets.connect(uri) as websocket:  # type: ignore
            await self._async_ws_joiner(websocket, device)
            await websocket.send(payload)
