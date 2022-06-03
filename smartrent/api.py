import logging
from typing import List, Optional, Union

import aiohttp

from .lock import DoorLock
from .sensor import LeakSensor
from .switch import BinarySwitch
from .thermostat import Thermostat
from .utils import Client

_LOGGER = logging.getLogger(__name__)


class API:
    """
    Represents overall SmartRent api

    ``email`` is the email address for your SmartRent account

    ``password`` you know what it is

    ``aiohttp_session`` (optional) uses the aiohttp_session that is passed in
    """

    def __init__(
        self, email: str, password: str, aiohttp_session: aiohttp.ClientSession = None
    ):
        self._device_list: List[
            Union[DoorLock, Thermostat, BinarySwitch, LeakSensor]
        ] = []
        self._email = email
        self._password = password
        self._session = aiohttp_session

        self.client: Client = Client(email, password, aiohttp_session)

    async def async_fetch_devices(self):
        """
        Fetches list of devices by calling SmartRent api
        """
        _LOGGER.info("Fetching devices via API...")
        await self.client.async_refresh_token()
        data = await self.client.async_get_devices_data()
        _LOGGER.info("Got devices!")

        for device in data:
            device_id = device.get("id")
            device_type = device.get("type")

            device_object: Union[Thermostat, DoorLock, BinarySwitch, LeakSensor] = None

            if device_type == "thermostat":
                device_object = Thermostat(device_id, self.client)

            elif device_type == "entry_control":
                device_object = DoorLock(device_id, self.client)

            elif device_type == "switch_binary":
                device_object = BinarySwitch(device_id, self.client)

            elif device_type == "sensor_notification":
                attr_names = [attr.get("name") for attr in device.get("attributes")]

                if "leak" in attr_names:
                    device_object = LeakSensor(device_id, self.client)

            if device_object:
                # pass in intial device config
                await device_object._async_fetch_state()

                # add device to device_list
                self._device_list.append(device_object)

    def get_device_list(
        self,
    ) -> List[Union[DoorLock, Thermostat, BinarySwitch, LeakSensor]]:
        """
        Gets list of all devices found
        """
        return self._device_list

    def get_locks(self) -> List[DoorLock]:
        """
        Gets list of DoorLocks
        """
        return self._list_maker(DoorLock)  # type: ignore

    def get_thermostats(self) -> List[Thermostat]:
        """
        Gets list of Thermostats
        """
        return self._list_maker(Thermostat)  # type: ignore

    def get_switches(self) -> List[BinarySwitch]:
        """
        Gets list of BinarySwitches
        """
        return self._list_maker(BinarySwitch)  # type: ignore

    def get_leak_sensors(self) -> List[LeakSensor]:
        """
        Gets list of LeakSensors
        """
        return self._list_maker(LeakSensor)  # type: ignore

    def _list_maker(
        self, to_find: Union[LeakSensor, BinarySwitch, Thermostat, DoorLock]
    ) -> List[Optional[Union[LeakSensor, BinarySwitch, Thermostat, DoorLock]]]:
        """
        Gets list of X type of item from ``device_list``
        """
        return [x for x in self._device_list if isinstance(x, to_find)]  # type: ignore


async def async_login(
    email: str, password: str, aiohttp_session: aiohttp.ClientSession = None
) -> API:
    """
    Logs into SmartRent and retruns an ``API`` object.

    Prepopulates ``API`` object with devices.

    ``email`` is the email address for your SmartRent account

    ``password`` you know what it is

    ``aiohttp_session`` (optional) uses the aiohttp_session that is passed in
    """

    smart_rent_api = API(email, password, aiohttp_session)
    await smart_rent_api.async_fetch_devices()

    return smart_rent_api
