from typing import Union
import logging

from .device import Device

_LOGGER = logging.getLogger(__name__)

class Thermostat(Device):
    def __init__(self, email: str, password: str, device_id: str):
        super().__init__(email, password, device_id)
        self.mode = None
        self.fan_mode = None
        self.cooling_setpoint = None
        self.heating_setpoint = None
        self.current_humidity = None
        self.current_temp = None


    def get_mode(self) -> Union[str, None]:
        '''
        Gets mode from thermostat
        '''
        return self.mode


    def get_fan_mode(self) -> Union[str, None]:
        '''
        Gets fan mode from thermostat
        '''
        return self.fan_mode


    def get_cooling_setpoint(self) -> Union[int, None]:
        '''
        Gets cooling setpoint from thermostat
        '''
        return self.cooling_setpoint


    def get_heating_setpoint(self) -> Union[int, None]:
        '''
        Gets heating setpoint from thermostat
        '''
        return self.heating_setpoint


    def get_current_humidity(self) -> Union[int, None]:
        '''
        Gets current humidity from thermostat
        '''
        return self.current_humidity


    def get_current_temp(self) -> Union[int, None]:
        '''
        Gets current temperature from thermostat
        '''
        return self.current_temp


    def fetch_state_helper(self, data:dict):
        '''
        Called when ``fetch_state`` returns info

        ``data`` is dict of info passed in by ``fetch_state``
        '''
        self._name = data['name']

        attrs = self.structure_attrs(data['attributes'])
        self.current_temp = int(attrs['MultiLvlSensor']['current_temp'])
        self.current_humidity = int(attrs['MultiLvlSensor']['current_humidity'])

        self.cooling_setpoint = int(attrs['ThermostatSetpoint']['cooling_setpoint'])
        self.heating_setpoint = int(attrs['ThermostatSetpoint']['heating_setpoint'])

        self.mode = attrs['ThermostatMode']['mode']
        self.fan_mode = attrs['ThermostatFanMode']['fan_mode']


    async def set_heating_setpoint(self, value: Union[str, int]):
        '''
        Sets heating setpoint

        ``value`` str or int representing temperature to set
        '''
        await self.send_command(
            attribute_name='heating_setpoint',
            value=value
        )

        self.heating_setpoint = int(value)


    async def set_cooling_setpoint(self, value: Union[str, int]):
        '''
        Sets cooling setpoint

        ``value`` str or int representing temperature to set
        '''
        await self.send_command(
            attribute_name='cooling_setpoint',
            value=value
        )

        self.cooling_setpoint = int(value)


    async def set_mode(self, mode: str):
        '''
        Sets thermostat mode

        ``mode`` str. One of ``['aux_heat', 'heat', 'cool', 'auto', 'off']``
        '''
        if mode not in ['aux_heat', 'heat', 'cool', 'auto', 'off']:
            return

        await self.send_command(
            attribute_name='mode',
            value=mode
        )

        self.mode = mode


    async def set_fan_mode(self, fan_mode: str):
        '''
        Sets thermostat fan mode

        ``value`` str. One of ``['auto', 'on']``
        '''
        if fan_mode not in ['on', 'auto']:
            return

        await self.send_command(
            attribute_name='fan_mode',
            value=fan_mode,
        )

        self.fan_mode = fan_mode


    def update_parser(self, event: dict) -> None:
        '''
        Called when ``update_state`` returns info

        ``event`` dict passed in from ``update_state``
        '''
        _LOGGER.info('Updating Thermostat')
        if event.get('type') == 'MultiLvlSensor':
            if event.get('name') == 'current_humidity':
                self.current_humidity = int(event.get('last_read_state'))

            if event.get('name') == 'current_temp':
                self.current_temp = int(event.get('last_read_state'))

        if event.get('type') == 'ThermostatMode':
            if event.get('name') == 'mode':
                self.mode = event.get('last_read_state')

        if event.get('type') == 'ThermostatFanMode':
            if event.get('name') == 'fan_mode':
                self.fan_mode = event.get('last_read_state')

        if event.get('type') == 'ThermostatSetpoint':
            if event.get('name') == 'heating_setpoint':
                self.heating_setpoint = int(event.get('last_read_state'))

            if event.get('name') == 'cooling_setpoint':
                self.cooling_setpoint = int(event.get('last_read_state'))
