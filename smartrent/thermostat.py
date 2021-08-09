from typing import Optional, Union
import logging

import aiohttp
from .device import Device

_LOGGER = logging.getLogger(__name__)

class Thermostat(Device):
    '''
    Represents Thermostat SmartRent device
    '''
    def __init__(
        self,
        email: str,
        password: str,
        device_id: int,
        aiohttp_session:aiohttp.ClientSession=None
    ):
        super().__init__(email, password, device_id, aiohttp_session)
        self._mode = None
        self._fan_mode = None
        self._cooling_setpoint = None
        self._heating_setpoint = None
        self._current_humidity = None
        self._current_temp = None


    def get_mode(self) -> Optional[str]:
        '''
        Gets mode from thermostat
        '''
        return self._mode


    def get_fan_mode(self) -> Optional[str]:
        '''
        Gets fan mode from thermostat
        '''
        return self._fan_mode


    def get_cooling_setpoint(self) -> Optional[int]:
        '''
        Gets cooling setpoint from thermostat
        '''
        return self._cooling_setpoint


    def get_heating_setpoint(self) -> Optional[int]:
        '''
        Gets heating setpoint from thermostat
        '''
        return self._heating_setpoint


    def get_current_humidity(self) -> Optional[int]:
        '''
        Gets current humidity from thermostat
        '''
        return self._current_humidity


    def get_current_temp(self) -> Optional[int]:
        '''
        Gets current temperature from thermostat
        '''
        return self._current_temp


    async def async_set_heating_setpoint(self, value: Union[str, int]):
        '''
        Sets heating setpoint

        ``value`` str or int representing temperature to set
        '''
        await self._async_send_command(
            attribute_name='heating_setpoint',
            value=value
        )

        self._heating_setpoint = int(value)


    async def async_set_cooling_setpoint(self, value: Union[str, int]):
        '''
        Sets cooling setpoint

        ``value`` str or int representing temperature to set
        '''
        await self._async_send_command(
            attribute_name='cooling_setpoint',
            value=value
        )

        self._cooling_setpoint = int(value)


    async def async_set_mode(self, mode: str):
        '''
        Sets thermostat mode

        ``mode`` str. One of ``['aux_heat', 'heat', 'cool', 'auto', 'off']``
        '''
        if mode not in ['aux_heat', 'heat', 'cool', 'auto', 'off']:
            return

        await self._async_send_command(
            attribute_name='mode',
            value=mode
        )

        self._mode = mode


    async def async_set_fan_mode(self, fan_mode: str):
        '''
        Sets thermostat fan mode

        ``value`` str. One of ``['auto', 'on']``
        '''
        if fan_mode not in ['on', 'auto']:
            return

        await self._async_send_command(
            attribute_name='fan_mode',
            value=fan_mode,
        )

        self._fan_mode = fan_mode


    def _fetch_state_helper(self, data:dict):
        '''
        Called when ``_async_fetch_state`` returns info

        ``data`` is dict of info passed in by ``_async_fetch_state``
        '''
        self._name = data['name']

        attrs = self._structure_attrs(data['attributes'])
        self._current_temp = int(attrs['current_temp'])
        self._current_humidity = int(attrs['current_humidity'])

        self._cooling_setpoint = int(attrs['cooling_setpoint'])
        self._heating_setpoint = int(attrs['heating_setpoint'])

        self._mode = attrs['mode']
        self._fan_mode = attrs['fan_mode']


    def _update_parser(self, event: dict) -> None:
        '''
        Called when ``_async_update_state`` returns info

        ``event`` dict passed in from ``_async_update_state``
        '''
        _LOGGER.info('Updating Thermostat')
        if event.get('name') == 'current_humidity':
            self._current_humidity = int(event.get('last_read_state'))

        if event.get('name') == 'current_temp':
            self._current_temp = int(event.get('last_read_state'))

        if event.get('name') == 'heating_setpoint':
            self._heating_setpoint = int(event.get('last_read_state'))

        if event.get('name') == 'cooling_setpoint':
            self._cooling_setpoint = int(event.get('last_read_state'))

        if event.get('name') == 'mode':
            self._mode = event.get('last_read_state')

        if event.get('name') == 'fan_mode':
            self._fan_mode = event.get('last_read_state')
