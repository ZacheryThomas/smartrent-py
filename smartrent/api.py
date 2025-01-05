import logging
from typing import TYPE_CHECKING, List, Optional, TypeVar

import aiohttp

from .device import Device
from .lock import DoorLock
from .sensor import LeakSensor, MotionSensor
from .switch import BinarySwitch, MultilevelSwitch
from .thermostat import Thermostat
from .utils import Client

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    ALL_DEVICE_TYPES = TypeVar("ALL_DEVICE_TYPES", bound=Device)


class API:
    """
    Represents overall SmartRent api

    ``email`` is the email address for your SmartRent account

    ``password`` you know what it is

    ``aiohttp_session`` (optional) uses the aiohttp_session that is passed in

    ``tfa_token`` (optional) tfa token to pass in for login
    """

    def __init__(
        self,
        email: str,
        password: str,
        aiohttp_session: aiohttp.ClientSession = None,
        tfa_token=None,
    ):
        self._device_list: List["ALL_DEVICE_TYPES"] = []  # type: ignore
        self.client: Client = Client(email, password, aiohttp_session, tfa_token)

    async def async_fetch_devices(self):
        """
        Fetches list of devices by calling SmartRent api
        """
        _LOGGER.info("Fetching devices via API...")
        data = await self.client.async_get_devices_data()
        _LOGGER.info("Got devices!")

        for device in data:
            device_id = device.get("id")
            device_type = device.get("type")

            device_object: Optional["ALL_DEVICE_TYPES"] = None

            if device_type == "thermostat":
                device_object = Thermostat(device_id, self.client)

            elif device_type == "entry_control":
                device_object = DoorLock(device_id, self.client)

            elif device_type == "switch_binary":
                device_object = BinarySwitch(device_id, self.client)

            elif device_type == "switch_multilevel":
                device_object = MultilevelSwitch(device_id, self.client)

            elif device_type == "sensor_notification":
                attr_names = [attr.get("name") for attr in device.get("attributes")]

                if "leak" in attr_names:
                    device_object = LeakSensor(device_id, self.client)

                if "motion_binary" in attr_names:
                    device_object = MotionSensor(device_id, self.client)

            if device_object:
                # pass in intial device config
                await device_object._async_fetch_state()

                # add device to device_list
                self._device_list.append(device_object)

    def get_device_list(
        self,
    ) -> List["ALL_DEVICE_TYPES"]:
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
        Gets list of BinarySwitches,
        Deprecating soon in favor of ``get_binary_switches``
        """
        _LOGGER.warning(
            'Function "get_switches" will be removed in a future update!'
            ' Please use "get_binary_switches" or "get_multilevel_switches".'
        )
        return self._list_maker(BinarySwitch)  # type: ignore

    def get_binary_switches(self) -> List[BinarySwitch]:
        """
        Gets list of BinarySwitches
        """
        return self._list_maker(BinarySwitch)  # type: ignore

    def get_multilevel_switches(self) -> List[MultilevelSwitch]:
        """
        Gets list of MultilevelSwitches
        """
        return self._list_maker(MultilevelSwitch)  # type: ignore

    def get_leak_sensors(self) -> List[LeakSensor]:
        """
        Gets list of LeakSensors
        """
        return self._list_maker(LeakSensor)  # type: ignore

    def get_motion_sensors(self) -> List[MotionSensor]:
        """
        Gets list of MotionSensors
        """
        return self._list_maker(MotionSensor)  # type: ignore

    def _list_maker(
        self,
        to_find: "ALL_DEVICE_TYPES",
    ) -> List[Optional["ALL_DEVICE_TYPES"]]:
        """
        Gets list of X type of item from ``device_list``
        """
        return [x for x in self._device_list if isinstance(x, to_find)]  # type: ignore


async def async_login(
    email: str,
    password: str,
    aiohttp_session: aiohttp.ClientSession = None,
    tfa_token: str = None,
) -> API:
    """
    Logs into SmartRent and retruns an ``API`` object.

    Prepopulates ``API`` object with devices.

    ``email`` is the email address for your SmartRent account

    ``password`` you know what it is

    ``aiohttp_session`` (optional) uses the aiohttp_session that is passed in

    ``tfa_token`` (optional) tfa token to pass in for login
    """

    smart_rent_api = API(email, password, aiohttp_session, tfa_token)
    await smart_rent_api.async_fetch_devices()

    return smart_rent_api
