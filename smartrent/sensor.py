import logging
from typing import Optional

from .device import Device
from .utils import Client

_LOGGER = logging.getLogger(__name__)


class Sensor(Device):
    """
    Represents a generic Sensor SmartRent device
    """

    def __init__(self, state_attribute: str, device_id: int, client: Client):
        super().__init__(device_id, client)
        self._active: Optional[bool] = None
        self._state_attribute = state_attribute

    def get_active(self) -> Optional[bool]:
        """
        Gets state from the sensor
        """
        return self._active

    def _fetch_state_helper(self, data: dict):
        """
        Called when ``_async_fetch_state`` returns info

        ``data`` is dict of info passed in by ``_async_fetch_state``
        """
        self._name = data["name"]

        attrs = self._structure_attrs(data["attributes"])

        self._active = bool(attrs[self._state_attribute] == "true")

    def _update_parser(self, event: dict):
        """
        Called when ``Client._async_update_state`` returns info

        ``event`` dict passed in from ``Client._async_update_state``
        """
        _LOGGER.info("Updating Sensor")

        if event.get("name") == self._state_attribute:
            self._active = bool(event["last_read_state"] == "true")


class LeakSensor(Sensor):
    """
    Represents SmartRent leak sensor
    """

    def __init__(self, device_id: int, client: Client):
        super().__init__("leak", device_id, client)


class MotionSensor(Sensor):
    """
    Represents SmartRent motion sensor
    """

    def __init__(self, device_id: int, client: Client):
        super().__init__("motion_binary", device_id, client)
