import inspect
import logging
from collections.abc import Callable
from typing import Any, Dict, List, Optional, Union

from .utils import Client

_LOGGER = logging.getLogger(__name__)


class Device:
    """
    Base class for SmartRent devices
    """

    def __init__(self, device_id: Union[str, int], client: Client):
        self._device_id = int(device_id)
        self._name: str = ""
        self._online: Optional[bool] = None
        self._battery_powered: Optional[bool] = None
        self._battery_level: Optional[int] = None
        self._update_callback_funcs: List[Callable[[None], None]] = []

        self._client: Client = client

    def __del__(self):
        self.stop_updater()

    def get_name(self) -> Optional[str]:
        """
        Gets the name of the device, if known
        """
        return self._name

    def get_online(self) -> Optional[bool]:
        """
        Gets if device is online or not
        """
        return self._online

    def get_battery_powered(self) -> Optional[bool]:
        """
        Gets if devices is battery powered
        """
        return self._battery_powered

    def get_battery_level(self) -> Optional[int]:
        """
        Gets devices battery level (assuming device is battery powered)
        """
        return self._battery_level

    @staticmethod
    def _structure_attrs(attrs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Converts device json object to hirearchical list of attributes

        ``attrs``: List of device attributes
        """
        structure: Dict[str, Any] = {}

        for attr in attrs:
            name: str = str(attr.get("name"))
            state: str = str(attr.get("state"))

            structure[name] = state

        _LOGGER.info("constructed attribute structure: %s", structure)
        return structure

    def _fetch_state_helper(self, data: Dict[str, str]):
        """
        Called by ``_async_fetch_state``

        Converts event dict to device param info
        """
        raise NotImplementedError

    async def _async_fetch_state(self):
        """
        Fetches device information from SmartRent api

        Calls ``_fetch_state_helper`` so device can parse out
        info and update it's state.

        Calls function passed into ``set_update_callback`` if it exists.
        """
        _LOGGER.info("%s: Fetching data from device endpoint...", self._name)
        device_data = await self._client.async_get_device_data(self._device_id)

        device_at_start = dict(vars(self))

        self._battery_level = device_data.get("battery_level")
        self._battery_powered = device_data.get("battery_powered")
        self._online = device_data.get("online")

        self._fetch_state_helper(device_data)

        device_at_end = dict(vars(self))

        # If device attrs updated, call callbacks
        if not device_at_start == device_at_end:
            await self._async_call_callbacks()

    def start_updater(self):
        """
        Allows device to update it's attrs in the background
        """
        self._client._subscribe_device_to_updater(self)

    def stop_updater(self):
        """
        Turns off automatic attr updates
        """
        self._client._unsubscribe_device_to_updater(self)

    def set_update_callback(self, func) -> None:
        """
        Allows callback to be fired when ``Client._async_update_state``
        or ``_async_fetch_state`` gets new information
        """

        self._update_callback_funcs.append(func)

    def unset_update_callback(self, func) -> None:
        """
        Removes callback from being fired when ``Client._async_update_state``
        or ``_async_fetch_state`` gets new information
        """
        try:
            self._update_callback_funcs.remove(func)
        except ValueError:
            pass

    def _update_parser(self, event: Dict[str, Any]) -> None:
        """
        Called by ``Client._async_update_state``

        Converts event dict to device attr info
        """
        raise NotImplementedError

    async def _update(self, event: Dict[str, Any]):
        """
        Recieves event dict, calls ``_update_parser`` for each device and callbacks
        """
        # handle updating of device attrs
        self._update_parser(event)

        # handle calling callbacks
        await self._async_call_callbacks()

    async def _async_call_callbacks(self):
        """
        Handles calling all callbacks
        """
        for func in self._update_callback_funcs:
            if inspect.iscoroutinefunction(func):
                await func()
            else:
                func()
