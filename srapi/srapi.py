import re
import json
import html
import logging
from typing import List
import aiohttp

from .lock import DoorLock
from .thermostat import Thermostat
from .utils import get_resident_page_text


_LOGGER = logging.getLogger(__name__)

class SmartRent():
    def __init__(self, email: str, password: str):
        self._device_list = []
        self._email = email
        self._password = password

    async def fetch_devices(self):
        '''
        Fetches list of devices by calling SmartRent api
        '''

        _LOGGER.info('Fetching devices...')
        resident_page_text = await get_resident_page_text(
            self._email,
            self._password
        )
        _LOGGER.info('Done fetching devices!')

        matches = re.search(r'bundle-props="(.*)" ', resident_page_text)
        if matches:
            data = html.unescape(matches[1])
            data = json.loads(data)

            for device in data.get('devices', []):
                device_id = device.get('id')
                device_type = device.get('type')

                if device_type == 'thermostat':
                    thermostat = Thermostat(self._email, self._password, device_id)
                    self._device_list.append(thermostat)

                if device_type == 'entry_control':
                    doorlock = DoorLock(self._email, self._password, device_id)
                    self._device_list.append(doorlock)
        else:
            raise Exception('Devices not retrieved! Loggin probably not successful.')

        if not self._device_list:
            raise Exception('Devices not retrieved! Loggin probably not successful.')


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

