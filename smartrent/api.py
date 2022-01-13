import logging
from typing import List, Union

import aiohttp

from .lock import DoorLock
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
        self._device_list = []
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

            device_object: Union[Thermostat, DoorLock] = None

            if device_type == "thermostat":
                device_object = Thermostat(device_id, self.client)

            elif device_type == "entry_control":
                device_object = DoorLock(device_id, self.client)

            if device_object:
                # pass in intial device config
                device_object._fetch_state_helper(device)

                # add device to device_list
                self._device_list.append(device_object)

    def get_locks(self) -> List[DoorLock]:
        """
        Gets list of DoorLocks
        """
        return [x for x in self._device_list if isinstance(x, DoorLock)]

    def get_thermostats(self) -> List[Thermostat]:
        """
        Gets list of Thermostats
        """
        return [x for x in self._device_list if isinstance(x, Thermostat)]


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
