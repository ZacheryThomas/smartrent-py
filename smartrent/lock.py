import logging
from typing import Optional

from .device import Device
from .utils import Client

_LOGGER = logging.getLogger(__name__)


class DoorLock(Device):
    """
    Represents Lock SmartRent device
    """

    def __init__(self, device_id: int, client: Client):
        super().__init__(device_id, client)
        self._locked: Optional[bool] = None
        self._notification: Optional[str] = None

    def get_notification(self) -> Optional[str]:
        """
        Notification message for lock
        """
        return self._notification

    def get_locked(self) -> Optional[bool]:
        """
        Gets state from lock
        """
        return self._locked

    async def async_set_locked(self, value: bool):
        """
        Sets state for lock
        """
        self._locked = value

        # Convert to lowercase just like SmartRent website does
        str_value = str(value).lower()

        await self._client._async_send_command(
            self, attribute_name="locked", value=str_value
        )

    def _fetch_state_helper(self, data: dict):
        """
        Called when ``_async_fetch_state`` returns info

        ``data`` is dict of info passed in by ``_async_fetch_state``
        """
        self._name = data["name"]

        attrs = self._structure_attrs(data["attributes"])

        self._locked = bool(attrs["locked"] == "true")
        self._notification = attrs["notifications"]

    def _update_parser(self, event: dict):
        """
        Called when ``Client._async_update_state`` returns info

        ``event`` dict passed in from ``Client._async_update_state``
        """
        _LOGGER.info("Updating DoorLock")

        if event.get("name") == "locked":
            self._locked = bool(event["last_read_state"] == "true")

        elif event.get("name") == "notifications":
            self._notification = event.get("last_read_state")
