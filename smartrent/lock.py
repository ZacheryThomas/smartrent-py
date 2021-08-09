from typing import Optional
import logging

import aiohttp
from .device import Device

_LOGGER = logging.getLogger(__name__)

class DoorLock(Device):
    '''
    Represents Lock SmartRent device
    '''
    def __init__(
        self,
        email: str,
        password: str,
        device_id: int,
        aiohttp_session:aiohttp.ClientSession=None
    ):
        super().__init__(email, password, device_id, aiohttp_session)
        self._locked = None
        self._notification = None


    def get_notification(self) -> Optional[str]:
        '''
        Notification message for lock
        '''
        return self._notification


    def get_locked(self) -> Optional[bool]:
        '''
        Gets state from lock
        '''
        return self._locked


    async def async_set_locked(self, value: bool):
        '''
        Sets state for lock
        '''

        self._locked = value

        # Convert to lowercase just like SmartRent website does
        value = 'true' if value else 'false'

        await self._async_send_command(
            attribute_name='locked',
            value=value
        )


    def _fetch_state_helper(self, data:dict):
        '''
        Called when ``_async_fetch_state`` returns info

        ``data`` is dict of info passed in by ``_async_fetch_state``
        '''
        self._name = data['name']

        attrs = self._structure_attrs(data['attributes'])

        self._locked = bool(attrs['locked'] == 'true')
        self._notification = attrs['notifications']


    def _update_parser(self, event: dict):
        '''
        Called when ``_async_update_state`` returns info

        ``event`` dict passed in from ``_async_update_state``
        '''
        _LOGGER.info('Updating DoorLock')
        if event.get('name') == 'locked':
            self._locked = bool(event['last_read_state'] == 'true')

        if event.get('name') == 'notifications':
            self._notification = event.get('last_read_state')
