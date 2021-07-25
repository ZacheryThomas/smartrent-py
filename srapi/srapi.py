import asyncio
import re
import json
import html
import logging

from typing import Union, List

import websockets
import aiohttp

_LOGGER = logging.getLogger(__name__)

SMARTRENT_URI   = 'wss://control.smartrent.com/socket/websocket?token={}&vsn=2.0.0'
JOINER_PAYLOAD  = '["null", "null", "devices:{device_id}", "phx_join", {{}}]'
COMMAND_PAYLOAD = '["null", "null", "devices:{device_id}", "update_attributes", ' \
                  '{{"device_id": {device_id}, ' \
                  '"attributes": [{{"name": "{attribute_name}", "value": "{value}"}}]}}]'


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


async def get_resident_page_text(
    email, password, aiohttp_session:aiohttp.ClientSession=None
) -> str:
    '''Gets full text from `/resident` page

    ``email`` is the email address for your SmartRent account

    ``password`` you know what it is

    ``aiohttp_session`` if provided uses the aiohttp_session that is passed in.
    This helps to avoid having to authenticate as often. Otherwise calling this method
    without a session ensures you will call the `/authentication/sessions` endpoint
    '''

    async with aiohttp.ClientSession() as session:
        session = aiohttp_session if aiohttp_session else session

        _LOGGER.info('Calling resident page')
        response = await session.get('https://control.smartrent.com/resident')
        resp_text = await response.text()

        if 'You must login to access this page.' in resp_text:
            _LOGGER.info(f'Attempting login')
            await session.post('https://control.smartrent.com/authentication/sessions', json={
                'email': email,
                'password': password
            })

            _LOGGER.info('Calling resident page again')
            response = await session.get('https://control.smartrent.com/resident')

        return await response.text()


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
        payload = COMMAND_PAYLOAD.format(
            attribute_name='heating_setpoint',
            value=int(value),
            device_id=self._device_id
        )
        await self.send_payload(payload)

        self.heating_setpoint = int(value)


    async def set_cooling_setpoint(self, value: Union[str, int]):
        '''
        Sets cooling setpoint

        ``value`` str or int representing temperature to set
        '''
        payload = COMMAND_PAYLOAD.format(
            attribute_name='cooling_setpoint',
            value=int(value),
            device_id=self._device_id
        )
        await self.send_payload(payload)

        self.cooling_setpoint = int(value)


    async def set_mode(self, mode: str):
        '''
        Sets thermostat mode

        ``value`` str. One of ``['aux_heat', 'heat', 'cool', 'auto', 'off']``
        '''
        if mode not in ['aux_heat', 'heat', 'cool', 'auto', 'off']:
            return

        payload = COMMAND_PAYLOAD.format(
            attribute_name='mode',
            value=mode,
            device_id=self._device_id
        )
        await self.send_payload(payload)

        self.mode = mode


    async def set_fan_mode(self, fan_mode: str):
        '''
        Sets thermostat fan mode

        ``value`` str. One of ``['auto', 'on']``
        '''
        if fan_mode not in ['on', 'auto']:
            return

        payload = COMMAND_PAYLOAD.format(
            attribute_name='fan_mode',
            value=fan_mode,
            device_id=self._device_id
        )
        await self.send_payload(payload)

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


class DoorLock(Device):
    def __init__(self, email: str, password: str, device_id: str):
        super().__init__(email, password, device_id)
        self.locked = None


    def get_locked(self) -> bool:
        '''
        Gets state from lock
        '''
        return self.locked


    async def set_locked(self, value: bool):
        '''
        Sets state for lock
        '''
        payload = COMMAND_PAYLOAD.format(
            attribute_name='locked',
            value=value,
            device_id=self._device_id
        )
        await self.send_payload(payload)

        self.locked = value


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

        self.locked = bool(attrs['DoorLock']['locked'] == 'true')
        self._notification = attrs['Notifications']['notifications']


    def update_parser(self, event: dict):
        '''
        Called when ``update_state`` returns info

        ``event`` dict passed in from ``update_state``
        '''
        _LOGGER.info('Updating DoorLock')
        if event.get('type') == 'DoorLock':
            self.locked = bool(event['last_read_state'] == 'true')

        if event.get('type') == 'Notifications':
            if event.get('name') == 'notifications':
                self._notification = event.get('last_read_state')

class Sensor(Device):
    def __init__(self, email: str, password: str, device_id: str):
        super().__init__(email, password, device_id)
        "TODO"
