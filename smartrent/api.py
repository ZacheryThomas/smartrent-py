import asyncio
import logging
from typing import List, Union

import aiohttp

from .lock import DoorLock
from .thermostat import Thermostat
from .utils import async_get_devices_data, async_login_to_api


_LOGGER = logging.getLogger(__name__)

class API():
    def __init__(self, email: str, password: str, aiohttp_session: aiohttp.ClientSession = None):
        self._device_list = []
        self._email = email
        self._password = password

        self._im_managing_session = not bool(aiohttp_session)
        self._session = aiohttp.ClientSession() if not aiohttp_session else aiohttp_session


    def __del__(self):
        if not self._session.closed and self._im_managing_session:
            _LOGGER.info('API closing session %s', self._session)
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
                # await device_object._async_update_token()
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


async def async_login(
    email: str,
    password: str,
    aiohttp_session: aiohttp.ClientSession = None
) -> API:
    '''
    Logs into SmartRent and retruns an `API` object

    ``email`` is the email address for your SmartRent account

    ``password`` you know what it is

    ``aiohttp_session`` (optional) uses the aiohttp_session that is passed in
    '''

    session = aiohttp_session if aiohttp_session else aiohttp.ClientSession()

    smart_rent_api = API(email, password, session)

    # if this function makes a session, let API object handle session cleanup
    smart_rent_api._im_managing_session = not bool(aiohttp_session)

    await async_login_to_api(email, password, session)
    await smart_rent_api.async_fetch_devices()

    return smart_rent_api
