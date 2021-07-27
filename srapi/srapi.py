import asyncio
import re
import json
import html
import logging
from typing import List, Union
import aiohttp

from .lock import DoorLock
from .thermostat import Thermostat
from .utils import async_get_devices_data, async_login_to_api


_LOGGER = logging.getLogger(__name__)

class API():
    def __init__(self, email: str, password: str, session: aiohttp.ClientSession = None):
        self._device_list = []
        self._email = email
        self._password = password
        self._session = aiohttp.ClientSession() if not session else session


    def __del__(self):
        asyncio.create_task(self._session.close())


    async def async_fetch_devices(self):
        '''
        Fetches list of devices by calling SmartRent api
        '''
        _LOGGER.info('Fetching devices...')
        data = await async_get_devices_data(
            self._email,
            self._password,
            self._session
        )

        for device in data.get('devices', []):
            device_id = device.get('id')
            device_type = device.get('type')

            device_object:Union['Thermostat', 'DoorLock'] = None

            if device_type == 'thermostat':
                device_object = Thermostat(self._email, self._password, device_id, self._session)

            elif device_type == 'entry_control':
                device_object = DoorLock(self._email, self._password, device_id, self._session)

            if device_object:
                # pass in intial device config
                device_object._fetch_state_helper(device)
                self._device_list.append(device_object)


    def get_locks(self) -> List['DoorLock']:
        '''
        Gets list of DoorLocks
        '''
        return [x for x in self._device_list if isinstance(x, DoorLock)]


    def get_thermostats(self) -> List['Thermostat']:
        '''
        Gets list of Thermostats
        '''
        return [x for x in self._device_list if isinstance(x, Thermostat)]


async def async_login(email: str, password: str, aiohttp_session: aiohttp.ClientSession=None):
    session = aiohttp.ClientSession() if not aiohttp_session else aiohttp_session

    sr = API(email, password)
    await async_login_to_api(email, password, session)
    await sr.async_fetch_devices()

    return sr
