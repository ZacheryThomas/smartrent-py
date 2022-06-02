import logging
from typing import Optional

from .device import Device
from .utils import Client

_LOGGER = logging.getLogger(__name__)


class LeakSensor(Device):
    """
    Represents LeakSensor SmartRent device
    """

    def __init__(self, device_id: int, client: Client):
        super().__init__(device_id, client)
        self._leak: Optional[bool] = None

    def get_leak(self) -> Optional[bool]:
        """
        Gets state from leak sensor
        """
        return self._leak

    def _fetch_state_helper(self, data: dict):
        """
        Called when ``_async_fetch_state`` returns info

        ``data`` is dict of info passed in by ``_async_fetch_state``
        """
        self._name = data["name"]

        attrs = self._structure_attrs(data["attributes"])

        self._leak = bool(attrs["leak"] == "true")

    def _update_parser(self, event: dict):
        """
        Called when ``Client._async_update_state`` returns info

        ``event`` dict passed in from ``Client._async_update_state``
        """
        _LOGGER.info("Updating Sensor")

        if event.get("name") == "leak":
            self._leak = bool(event["last_read_state"] == "true")
