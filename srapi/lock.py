from typing import Union
import logging

from .device import Device

_LOGGER = logging.getLogger(__name__)

class DoorLock(Device):
    def __init__(self, email: str, password: str, device_id: str):
        super().__init__(email, password, device_id)
        self._locked = None


    def get_locked(self) -> bool:
        '''
        Gets state from lock
        '''
        return self._locked


    async def set_locked(self, value: bool):
        '''
        Sets state for lock
        '''
        await self.send_command(
            attribute_name='locked',
            value=value
        )

        self._locked = value


    def get_notification(self) -> str:
        '''
        Notification message for lock
        '''
        return self._notification


    def fetch_state_helper(self, data:dict):
        '''
        Called when ``fetch_state`` returns info

        ``data`` is dict of info passed in by ``fetch_state``
        '''
        self._name = data['name']

        attrs = self.structure_attrs(data['attributes'])

        self._locked = bool(attrs['DoorLock']['locked'] == 'true')
        self._notification = attrs['Notifications']['notifications']


    def update_parser(self, event: dict):
        '''
        Called when ``update_state`` returns info

        ``event`` dict passed in from ``update_state``
        '''
        _LOGGER.info('Updating DoorLock')
        if event.get('type') == 'DoorLock':
            self._locked = bool(event['last_read_state'] == 'true')

        if event.get('type') == 'Notifications':
            if event.get('name') == 'notifications':
                self._notification = event.get('last_read_state')