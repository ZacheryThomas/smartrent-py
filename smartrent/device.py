import json
import asyncio
import inspect

from typing import Union
import logging

import websockets
import aiohttp
from .utils import async_get_token, async_get_devices_data

_LOGGER = logging.getLogger(__name__)

SMARTRENT_WEBSOCKET_URI   = 'wss://control.smartrent.com/socket/websocket?token={}&vsn=2.0.0'
JOINER_PAYLOAD            = '["null", "null", "devices:{device_id}", "phx_join", {{}}]'
COMMAND_PAYLOAD           = '["null", "null", "devices:{device_id}", "update_attributes", ' \
                            '{{"device_id": {device_id}, ' \
                            '"attributes": [{{"name": "{attribute_name}", "value": "{value}"}}]}}]'

class Device():
    '''
    Base class for SmartRent devices
    '''
    def __init__(
        self,
        email:str,
        password:str,
        device_id:Union[str, int],
        aiohttp_session:aiohttp.ClientSession=None
    ):
        self._device_id = int(device_id)
        self._name: str = ''
        self._token: str = None
        self._email =  email
        self._password = password
        self._update_callback_func = None
        self._updater_task = None

        self._im_managing_session = not bool(aiohttp_session)
        self._session = aiohttp.ClientSession() if not aiohttp_session else aiohttp_session


    def __del__(self):
        if not self._session.closed and self._im_managing_session:
            _LOGGER.info('%s: closing session %s', self._name, self._session)
            asyncio.create_task(self._session.close())

    @staticmethod
    def _structure_attrs(attrs: list):
        '''
        Converts device json object to hirearchical list of attributes

        ``attrs``: List of device attributes
        '''
        structure = {}

        for attr in attrs:
            name = attr.get('name')
            last_read_state = attr.get('last_read_state')

            structure[name] = last_read_state
        return structure


    def _fetch_state_helper(self, data: dict):
        '''
        Called by ``_async_fetch_state``

        Converts event dict to device param info
        '''
        raise NotImplementedError


    async def _async_fetch_state(self):
        '''
        Fetches device information from SmartRent `/resident` page

        Calls ``_fetch_state_helper`` so device can parse out info and update its state.

        Calls function passed into ``set_update_callback`` if it exists.
        '''
        _LOGGER.info('%s: Fetching Status res page call...', self._name)
        data = await async_get_devices_data(self._email, self._password, self._session)

        # Find device id that belongs to me then call _fetch_state_helper
        for device in data['devices']:
            if device['id'] == self._device_id:
                self._fetch_state_helper(device)

                if self._update_callback_func:
                    if inspect.iscoroutinefunction(self._update_callback_func):
                        await self._update_callback_func()
                    else:
                        self._update_callback_func()


    async def _async_update_token(self):
        '''
        Updates the internal websocket token for the device
        '''
        _LOGGER.info('%s: Update Token res page call...', self._name)
        self._token = await async_get_token(self._email, self._password, self._session)

    def start_updater(self):
        '''
        Starts running ``update_state`` in the background
        '''
        _LOGGER.info('%s: Starting updater task', self._name)
        self._updater_task = asyncio.create_task(self._async_update_state())


    def stop_updater(self):
        '''
        Stops running ``update_state`` in the background
        '''
        if self._updater_task:
            _LOGGER.info('%s: Stopping updater task', self._name)
            self._updater_task.cancel()


    def set_update_callback(self, func) -> None:
        '''
        Allows callback to be fired when ``_async_update_state``
        or ``_async_fetch_state`` gets new information
        '''
        self._update_callback_func = func


    def _update_parser(self, event: dict) -> None:
        '''
        Called by ``_async_update_state``

        Converts event dict to device param info
        '''
        raise NotImplementedError


    async def _async_update_state(self):
        '''
        Connects to SmartRent websocket and listens for updates.
        To be ran in the background. You can call ``start_updater`` and ``stop_updater``
        to turn ``_async_update_state`` on or off.

        Calls ``_update_parser`` method for device when event is found
        '''
        await self._async_update_token()

        uri = SMARTRENT_WEBSOCKET_URI.format(self._token)

        async with websockets.connect(uri) as websocket:
            joiner = JOINER_PAYLOAD.format(device_id=self._device_id)
            await websocket.send(joiner)

            while True:
                try:
                    resp = await websocket.recv()

                    formatted_resp = json.loads(f'{{"data":{resp}}}')['data'][4]

                    if formatted_resp.get('type'):
                        event = (
                            f'{formatted_resp.get("type", ""):<15}: '
                            f'{formatted_resp.get("name", ""):<15}: '
                            f'{formatted_resp.get("last_read_state", ""):<20}'
                        )
                        _LOGGER.info('%s %s',self._name, event)
                    else:
                        _LOGGER.info('%s %s',self._name, resp)

                    self._update_parser(formatted_resp)

                    if self._update_callback_func:
                        if inspect.iscoroutinefunction(self._update_callback_func):
                            await self._update_callback_func()
                        else:
                            self._update_callback_func()

                except (
                    websockets.exceptions.ConnectionClosedError,
                    websockets.exceptions.ConnectionClosedOK
                ) as exc:
                    _LOGGER.warning('%s: Got excpetion: %s', self._name, exc)

                    _LOGGER.info('%s: Getting new token', self._name)
                    await self._async_update_token()

                    # Lets fetch device state just to make sure
                    # we didn't miss anything wile the socket was down
                    _LOGGER.info('%s: Fetching current device status...', self._name)
                    await self._async_fetch_state()

                    _LOGGER.info('%s: Reconnecting to Websocket...', self._name)
                    uri = SMARTRENT_WEBSOCKET_URI.format(self._token)

                    websocket = await websockets.connect(uri)
                    _LOGGER.info('%s: Connected!', self._name)

                    _LOGGER.info(
                        '%s: Joining topic for %s:%s ...',
                        self._name,
                        self._name,
                        self._device_id
                    )
                    joiner = JOINER_PAYLOAD.format(device_id=self._device_id)
                    await websocket.send(joiner)


    async def _async_send_command(self, attribute_name:str, value:str):
        '''
        Sends command to SmartRent websocket

        ``attribute_name`` string of attribute to change
        ``value`` value for that attribute to be changed to
        '''
        payload = COMMAND_PAYLOAD.format(
            attribute_name=attribute_name,
            value=value,
            device_id=self._device_id
        )

        await self._async_send_payload(payload)


    async def _async_send_payload(self, payload:str):
        '''
        Sends payload to SmartRent websocket

        ``payload`` string of device attributes
        '''
        _LOGGER.info('sending payload %s', payload)

        joiner = JOINER_PAYLOAD.format(device_id=self._device_id)
        uri = SMARTRENT_WEBSOCKET_URI.format(self._token)

        async def sender(uri: str, payload: str):
            async with websockets.connect(uri) as websocket:
                # Join topic given device id
                await websocket.send(joiner)
                # Send payload
                await websocket.send(payload)

        try:
            uri = SMARTRENT_WEBSOCKET_URI.format(self._token)

            await sender(uri, payload)

        except websockets.exceptions.InvalidStatusCode as exc:
            _LOGGER.warning('Issue during send_payload: %s', exc)

            # update token once
            await self._async_update_token()

            uri = SMARTRENT_WEBSOCKET_URI.format(self._token)

            await sender(uri, payload)
