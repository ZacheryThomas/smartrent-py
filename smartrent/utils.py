import asyncio
import logging
from typing import List

import aiohttp

_LOGGER = logging.getLogger(__name__)

SMARTRENT_BASE_URI = "https://control.smartrent.com/api/v2/"
SMARTRENT_SESSIONS_URI = SMARTRENT_BASE_URI + "sessions"
SMARTRENT_TOKENS_URI = SMARTRENT_BASE_URI + "tokens"
SMARTRENT_HUBS_URI = SMARTRENT_BASE_URI + "hubs"
SMARTRENT_HUBS_ID_URI = SMARTRENT_BASE_URI + "hubs/{}/devices"


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
    Represents Client for SmartRent http api.
    Usually shared between multiple devices for best performance.

    ``email`` is the email address for your SmartRent account

    ``password`` you know what it is

    ``aiohttp_session`` (optional) uses the aiohttp_session that is passed in
    """

    def __init__(
        self, email: str, password: str, aiohttp_session: aiohttp.ClientSession = None
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

    async def async_get_devices_data(self) -> List[dict]:
        """
        Gets list of device dictonaries from SmartRent's api.
        Also handles retry if token is bad
        """
        if not self._token:
            await self.async_refresh_token()

        try:
            res = await self._async_get_devices_data()
        except InvalidAuthError:
            _LOGGER.warning("InvalidAuth detected. Trying again with updated token...")
            await self.async_refresh_token()

            res = await self._async_get_devices_data()

        return res

    async def _async_get_devices_data(self) -> List[dict]:
        """
        Gets list of device dictonaries from SmartRent's api
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

    def get_current_token(self) -> str:
        """Returns current token"""
        return self._token

    async def async_refresh_token(self) -> None:
        """
        Refreshes API token from SmartRents
        """
        response = {}
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

        if not response.get("errors"):
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

    async def _async_refresh_tokens_via_refresh_token(self) -> dict:
        """
        Calls api endpoint to get tokens given a refresh token
        """
        _LOGGER.info("Refreshing tokens with refresh token")
        headers = {"authorization-x-refresh": self._refresh_token}
        resp = await self._aiohttp_session.post(SMARTRENT_TOKENS_URI, headers=headers)
        return await resp.json()
