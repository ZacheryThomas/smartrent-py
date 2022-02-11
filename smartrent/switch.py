from typing import Optional
import logging

from .device import Device
from .utils import Client

_LOGGER = logging.getLogger(__name__)


class BinarySwitch(Device):
    """
    Represents BinarySwitch SmartRent device
    """

    def __init__(self, device_id: int, client: Client):
        super().__init__(device_id, client)
        self._on = None

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
        value = str(value).lower()

        await self._async_send_command(attribute_name="on", value=value)

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
        Called when ``_async_update_state`` returns info

        ``event`` dict passed in from ``_async_update_state``
        """
        _LOGGER.info("Updating Switch")

        if event.get("name") == "on":
            self._on = bool(event["last_read_state"] == "true")
