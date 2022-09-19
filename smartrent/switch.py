import logging
from typing import Optional

from .device import Device
from .utils import Client

_LOGGER = logging.getLogger(__name__)


class BinarySwitch(Device):
    """
    Represents BinarySwitch SmartRent device
    """

    def __init__(self, device_id: int, client: Client):
        super().__init__(device_id, client)
        self._on: Optional[bool] = None

    def get_on(self) -> Optional[bool]:
        """
        Gets state from switch
        """
        return self._on

    async def async_set_on(self, value: bool):
        """
        Sets state for switch
        """
        self._on = value

        # Convert to lowercase just like SmartRent website does
        str_value = str(value).lower()

        await self._client._async_send_command(
            self, attribute_name="on", value=str_value
        )

    def _fetch_state_helper(self, data: dict):
        """
        Called when ``_async_fetch_state`` returns info

        ``data`` is dict of info passed in by ``_async_fetch_state``
        """
        self._name = data["name"]

        attrs = self._structure_attrs(data["attributes"])

        self._on = bool(attrs["on"] == "true")

    def _update_parser(self, event: dict):
        """
        Called when ``Client._async_update_state`` returns info

        ``event`` dict passed in from ``Client._async_update_state``
        """
        _LOGGER.info("Updating Switch")

        if event.get("name") == "on":
            self._on = bool(event["last_read_state"] == "true")


class MultilevelSwitch(Device):
    """
    Represents MultilevelSwitch SmartRent device
    """

    def __init__(self, device_id: int, client: Client):
        super().__init__(device_id, client)
        self._level: Optional[int] = None

    def get_level(self) -> Optional[int]:
        """
        Gets state from multilevel switch
        """
        return self._level

    async def async_set_level(self, value: int):
        """
        Sets state for multilevel switch
        """
        await self._client._async_send_command(
            self, attribute_name="level", value=str(int(value))
        )

        self._level = int(value)

    def _fetch_state_helper(self, data: dict):
        """
        Called when ``_async_fetch_state`` returns info

        ``data`` is dict of info passed in by ``_async_fetch_state``
        """
        self._name = data["name"]

        attrs = self._structure_attrs(data["attributes"])

        def float_to_int(x: Optional[str]):
            if x and x != "None":
                return int(float(x))

        self._level = float_to_int(attrs["level"])

    def _update_parser(self, event: dict):
        """
        Called when ``Client._async_update_state`` returns info

        ``event`` dict passed in from ``Client._async_update_state``
        """
        _LOGGER.info("Updating Multilevel Switch")

        if event.get("name") == "level":
            self._level = int(event["last_read_state"])
