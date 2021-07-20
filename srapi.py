import asyncio
import re
import json
import html

from typing import Union, List

import requests
import websockets


SMARTRENT_URI   = "wss://control.smartrent.com/socket/websocket?token={}&vsn=2.0.0"
JOINER_PAYLOAD  = '["null", "null", "devices:{device_id}", "phx_join", {{}}]'
COMMAND_PAYLOAD = '["null", "null", "devices:{device_id}", "update_attributes", ' \
                  '{{"device_id": {device_id}, ' \
                  '"attributes": [{{"name": "{attribute_name}", "value": "{value}"}}]}}]'


class SmartRent():
    def __init__(self, email: str, password: str):
        self.device_list = []

        sess = requests.session()

        sess.post('https://control.smartrent.com/authentication/sessions', json={
            'email': email,
            'password': password
        })

        resident_page = sess.get('https://control.smartrent.com/resident')

        matches = re.search(r'bundle-props="(.*)" ', resident_page.text)
        if matches:
            data = html.unescape(matches[1])
            data = json.loads(data)

            for device in data['devices']:
                device_id = device['id']
                device_type = device['type']

                if device_type == 'thermostat':
                    thermostat = Thermostat(email, password, device_id)
                    self.device_list.append(thermostat)

                if device_type == 'entry_control':
                    doorlock = DoorLock(email, password, device_id)
                    self.device_list.append(doorlock)
        else:
            raise Exception('Devices not retrieved! Loggin probably not successful.')


    def get_locks(self) -> List['DoorLock']:
        return [x for x in self.device_list if isinstance(x, DoorLock)]


    def get_thermostats(self) -> List['Thermostat']:
        return [x for x in self.device_list if isinstance(x, Thermostat)]


class Device():
    def __init__(self, email:str, password:str, device_id:Union[str, int]):
        self.device_id = int(device_id)
        self.name = ''
        self.notification = ''
        self._email =  email
        self._password = password

        # update token once
        self.update_token()

        # fetch device status from SmartRent
        self.fetch_status()

        # run updater in background
        asyncio.create_task(self.update_state())


    @staticmethod
    def structure_attrs(attrs: dict):
        structure = {}

        for attr in attrs:
            type_val = attr.get('type')
            name = attr.get('name')
            last_read_state = attr.get('last_read_state')

            if type_val not in structure:
                structure[type_val] = {}

            structure[type_val][name] = last_read_state
        return structure


    def fetch_status_helper(self, data: dict):
        raise NotImplementedError


    def fetch_status(self):
        session = requests.session()

        session.post('https://control.smartrent.com/authentication/sessions', json={
            'email': self._email,
            'password': self._password
        })

        resident_page = session.get('https://control.smartrent.com/resident')

        matches = re.search(r'bundle-props="(.*)" ', resident_page.text)
        if matches:
            data = html.unescape(matches[1])
            data = json.loads(data)

            for device in data['devices']:
                if device['id'] == self.device_id:
                    self.fetch_status_helper(device)
        else:
            print(resident_page.text)
            raise Exception('Devices not retrieved! Loggin probably not successful.')


    def update_token(self):
        session = requests.session()

        session.post('https://control.smartrent.com/authentication/sessions', json={
            'email': self._email,
            'password': self._password
        })

        resident_page = session.get('https://control.smartrent.com/resident')

        matches = re.search(r'websocketAccessToken = "(.*)"', resident_page.text)

        if matches:
            self.token = matches[1]
        else:
            print(resident_page.text)
            raise Exception('Token not retrieved! Loggin probably not successful.')


    async def update_state(self):
        uri = SMARTRENT_URI.format(self.token)

        async with websockets.connect(uri) as websocket:
            joiner = JOINER_PAYLOAD.format(device_id=self.device_id)
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
                        print(event)
                    else:
                        print(resp)

                    self.update_parser(formatted_resp)

                except (
                    websockets.exceptions.ConnectionClosedError,
                    websockets.exceptions.ConnectionClosedOK
                ) as exc:
                    print(f'Got excpetion: {exc}')

                    print('Getting new token')
                    self.update_token()

                    print('Fetching current device status...')
                    self.fetch_status()

                    print('Reconnecting...')
                    uri = SMARTRENT_URI.format(self.token)

                    websocket = await websockets.connect(uri)
                    print('Connected!')

                    print(f'Joining topic for {self.name}:{self.device_id} ...')
                    joiner = JOINER_PAYLOAD.format(device_id=self.device_id)
                    await websocket.send(joiner)


    async def send_payload(self, payload):
        uri = SMARTRENT_URI.format(self.token)

        async with websockets.connect(uri) as websocket:
            joiner = JOINER_PAYLOAD.format(device_id=self.device_id)
            # Join topic given device id
            await websocket.send(joiner)

            # Send payload
            await websocket.send(payload)


    def update_parser(self, event: dict) -> None:
        raise NotImplementedError


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
        return self.mode


    def get_fan_mode(self) -> Union[str, None]:
        return self.fan_mode


    def get_cooling_setpoint(self) -> Union[int, None]:
        return self.cooling_setpoint


    def get_heating_setpoint(self) -> Union[int, None]:
        return self.current_temp


    def get_current_humidity(self) -> Union[int, None]:
        return self.heating_setpoint


    def get_current_temp(self) -> Union[int, None]:
        return self.current_temp


    def fetch_status_helper(self, data:dict):
        self.name = data['name']

        attrs = self.structure_attrs(data['attributes'])
        self.current_temp = attrs['MultiLvlSensor']['current_temp']
        self.current_humidity = attrs['MultiLvlSensor']['current_humidity']

        self.cooling_setpoint = attrs['ThermostatSetpoint']['cooling_setpoint']
        self.heating_setpoint = attrs['ThermostatSetpoint']['heating_setpoint']

        self.mode = attrs['ThermostatMode']['mode']
        self.fan_mode = attrs['ThermostatFanMode']['fan_mode']


    async def set_heating_setpoint(self, value: Union[str, int]):
        payload = COMMAND_PAYLOAD.format(
            attribute_name='heating_setpoint',
            lock=value,
            device_id=self.device_id
        )
        await self.send_payload(payload)

        self.heating_setpoint = int(value)


    async def set_cooling_setpoint(self, value: Union[str, int]):
        payload = COMMAND_PAYLOAD.format(
            attribute_name='cooling_setpoint',
            value=value,
            device_id=self.device_id
        )
        await self.send_payload(payload)

        self.cooling_setpoint = int(value)


    async def set_mode(self, mode: str):
        if mode not in ['aux_heat', 'heat', 'cool', 'auto', 'off']:
            return

        payload = COMMAND_PAYLOAD.format(
            attribute_name='mode',
            value=mode,
            device_id=self.device_id
        )
        await self.send_payload(payload)

        self.mode = mode


    async def set_fan_mode(self, fan_mode: str):
        if fan_mode not in ['on', 'auto']:
            return

        payload = COMMAND_PAYLOAD.format(
            attribute_name='fan_mode',
            value=fan_mode,
            device_id=self.device_id
        )
        await self.send_payload(payload)

        self.fan_mode = fan_mode


    def update_parser(self, event: dict) -> None:
        print('Updating Thermostat')
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
        return self.locked


    async def set_locked(self, value: bool):
        payload = COMMAND_PAYLOAD.format(
            attribute_name='locked',
            value=value,
            device_id=self.device_id
        )
        await self.send_payload(payload)

        self.locked = value


    def get_notification(self) -> str:
        return self.notification


    def fetch_status_helper(self, data:dict):
        self.name = data['name']

        attrs = self.structure_attrs(data['attributes'])

        self.locked = bool(attrs['DoorLock']['locked'] == 'true')
        self.notification = attrs['Notifications']['notifications']


    def update_parser(self, event: dict):
        print('Updating DoorLock')
        if event.get('type') == 'DoorLock':
            self.locked = bool(event['last_read_state'] == 'true')

        if event.get('type') == 'Notifications':
            if event.get('name') == 'notifications':
                self.notification = event.get('last_read_state')

class Sensor(Device):
    def __init__(self, email: str, password: str, device_id: str):
        super().__init__(email, password, device_id)
        "TODO"
