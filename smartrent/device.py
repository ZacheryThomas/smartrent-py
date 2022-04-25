import inspect
import logging

from typing import Union, List, Dict
from .utils import Client

_LOGGER = logging.getLogger(__name__)


class Device:
    """
    Base class for SmartRent devices
    """

    def __init__(self, device_id: Union[str, int], client: Client):
        self._device_id = int(device_id)
        self._name: str = ""
        self._update_callback_funcs = []
        self._updater_task = None

        self._client: Client = client

    def __del__(self):
        self.stop_updater()

    @staticmethod
    def _structure_attrs(attrs: List[Dict[str, any]]) -> Dict[str, any]:
        """
        Converts device json object to hirearchical list of attributes

        ``attrs``: List of device attributes
        """
        structure = {}

        for attr in attrs:
            name = attr.get("name")
            state = attr.get("state")

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

        Calls ``_fetch_state_helper`` so device can parse out info and update its state.

        Calls function passed into ``set_update_callback`` if it exists.
        """
        _LOGGER.info("%s: Fetching data from device endpoint...", self._name)
        data = await self._client.async_get_devices_data()

        # Find device id that belongs to me then call _fetch_state_helper
        for device in data:
            if device["id"] == self._device_id:
                self._fetch_state_helper(device)

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
        Allows callback to be fired when ``_async_update_state``
        or ``_async_fetch_state`` gets new information
        """

        self._update_callback_funcs.append(func)

    def unset_update_callback(self, func) -> None:
        """
        Removes callback from being fired when ``_async_update_state``
        or ``_async_fetch_state`` gets new information
        """

        try:
            self._update_callback_funcs.remove(func)
        except ValueError:
            pass

    def _update_parser(self, event: Dict[str, any]) -> None:
        """
        Called by ``_async_update_state``

        Converts event dict to device attr info
        """
        raise NotImplementedError

    async def _update(self, event: Dict[str, any]):
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
