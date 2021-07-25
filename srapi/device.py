import re
import json
import html
import asyncio

from typing import Union
import logging

import websockets
import aiohttp
from .utils import get_resident_page_text

_LOGGER = logging.getLogger(__name__)

SMARTRENT_URI   = 'wss://control.smartrent.com/socket/websocket?token={}&vsn=2.0.0'
JOINER_PAYLOAD  = '["null", "null", "devices:{device_id}", "phx_join", {{}}]'
COMMAND_PAYLOAD = '["null", "null", "devices:{device_id}", "update_attributes", ' \
                  '{{"device_id": {device_id}, ' \
                  '"attributes": [{{"name": "{attribute_name}", "value": "{value}"}}]}}]'

class Device():
    def __init__(self, email:str, password:str, device_id:Union[str, int]):
        self._device_id = int(device_id)
        self._name: str = ''
        self._notification: str = ''
        self._token: str = None
        self._email =  email
        self._password = password
        self._session = aiohttp.ClientSession()
        self._update_callback_func = None

        self._updater_task = None

    @staticmethod
    def structure_attrs(attrs: list):
        '''
        Converts device json object to hirearchical list of attributes

        ``attrs``: List of device attributes
        '''
        structure = {}

        for attr in attrs:
            type_val = attr.get('type')
            name = attr.get('name')
            last_read_state = attr.get('last_read_state')

            if type_val not in structure:
                structure[type_val] = {}

            structure[type_val][name] = last_read_state
        return structure


    def fetch_state_helper(self, data: dict):
        '''
        Called by ``fetch_state``

        Converts event dict to device param info
        '''
        raise NotImplementedError


    async def fetch_state(self):
        '''
        Fetches device information from SmartRent `/resident` page

        Calls ``fetch_state_helper`` so device can parse out info and update its state.

        Calls function passed into ``set_update_callback`` if it exists.
        '''
        _LOGGER.info(f'{self._name}: Fetching Status res page call...')
        resident_page_text = await get_resident_page_text(
            self._email,
            self._password,
            self._session
        )
        _LOGGER.info(f'{self._name}: Done Fetching Status')

        # Device states stored in json object called `bundle-props`
        matches = re.search(r'bundle-props="(.*)" ', resident_page_text)
        if matches:
            data = html.unescape(matches[1])
            data = json.loads(data)

            # Find device id that belongs to me then call fetch_state_helper
            for device in data['devices']:
                if device['id'] == self._device_id:
                    self.fetch_state_helper(device)
                    if self._update_callback_func:
                        self._update_callback_func()
        else:
            _LOGGER.error(resident_page_text)
            raise Exception('Devices not retrieved! Loggin probably not successful.')


    async def update_token(self):
        '''
        Updates the internal websocket token for the device
        '''
        _LOGGER.info(f'{self._name}: Update Token res page call...')
        resident_page_text = await get_resident_page_text(
            self._email,
            self._password,
            self._session
        )
        _LOGGER.info(f'{self._name}: Done Updating Token')
        matches = re.search(r'websocketAccessToken = "(.*)"', resident_page_text)
        if matches:
            self._token = matches[1]
        else:
            _LOGGER.error(resident_page_text)
            raise Exception('Token not retrieved! Loggin probably not successful.')


    def start_updater(self):
        '''
        Starts running ``update_state`` in the background
        '''
        _LOGGER.info('Starting updater task')
        self._updater_task = asyncio.create_task(self.update_state())


    def stop_updater(self):
        '''
        Stops running ``update_state`` in the background
        '''
        if self._updater_task:
            _LOGGER.info('Stopping updater task')
            self._updater_task.cancel()


    def set_update_callback(self, func) -> None:
        '''
        Allows callback to be fired when ``update_state`` or ``fetch_state`` gets new information
        '''
        self._update_callback_func = func


    def update_parser(self, event: dict) -> None:
        '''
        Called by ``update_state``

        Converts event dict to device param info
        '''
        raise NotImplementedError


    async def update_state(self):
        '''
        Connects to SmartRent websocket and listens for updates.
        To be ran in the background. You can call ``start_updater`` and ``stop_updater``
        to turn ``update_state`` on or off.

        Calls ``update_parser`` method for device when event is found
        '''
        await self.update_token()

        uri = SMARTRENT_URI.format(self._token)

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
                        _LOGGER.info(event)
                    else:
                        _LOGGER.info(resp)

                    self.update_parser(formatted_resp)
                    if self._update_callback_func:
                        self._update_callback_func()

                except (
                    websockets.exceptions.ConnectionClosedError,
                    websockets.exceptions.ConnectionClosedOK
                ) as exc:
                    _LOGGER.warn(f'{self._name}: Got excpetion: {exc}')

                    _LOGGER.info(f'{self._name}: Getting new token')
                    await self.update_token()

                    _LOGGER.info(f'{self._name}: Fetching current device status...')
                    await self.fetch_state()

                    _LOGGER.info(f'{self._name}: Reconnecting to Websocket...')
                    uri = SMARTRENT_URI.format(self._token)

                    websocket = await websockets.connect(uri)
                    _LOGGER.info(f'{self._name}: Connected!')

                    _LOGGER.info(f'{self._name}: Joining topic for {self._name}:{self._device_id} ...')
                    joiner = JOINER_PAYLOAD.format(device_id=self._device_id)
                    await websocket.send(joiner)


    async def send_command(self, attribute_name:str, value:str):
        '''
        Sends command to SmartRent websocket

        ``attribute_name`` string of attribute to change
        ``value`` value for that attribute to be changed to
        '''
        payload = COMMAND_PAYLOAD.format(
            attribute_name=attribute_name,
            value=int(value),
            device_id=self._device_id
        )

        await self.send_payload(payload)


    async def send_payload(self, payload:str):
        '''
        Sends payload to SmartRent websocket

        ``payload`` string of device attributes
        '''

        try:
            uri = SMARTRENT_URI.format(self._token)

            async with websockets.connect(uri) as websocket:
                joiner = JOINER_PAYLOAD.format(device_id=self._device_id)
                # Join topic given device id
                await websocket.send(joiner)

                # Send payload
                await websocket.send(payload)

        except websockets.exceptions.InvalidStatusCode as e:
            _LOGGER.warn(f'Issue during send_payload: {e}')

            # update token once
            await self.update_token()

            uri = SMARTRENT_URI.format(self._token)

            async with websockets.connect(uri) as websocket:
                joiner = JOINER_PAYLOAD.format(device_id=self._device_id)
                # Join topic given device id
                await websocket.send(joiner)

                # Send payload
                await websocket.send(payload)
