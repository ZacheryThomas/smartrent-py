import logging
from typing import Optional

from .device import Device
from .utils import Client

_LOGGER = logging.getLogger(__name__)


class Thermostat(Device):
    """
    Represents Thermostat SmartRent device
    """

    def __init__(self, device_id: int, client: Client):
        super().__init__(device_id, client)
        self._mode: Optional[str] = None
        self._fan_mode: Optional[str] = None
        self._operating_state: Optional[str] = None
        self._cooling_setpoint: Optional[int] = None
        self._heating_setpoint: Optional[int] = None
        self._current_humidity: Optional[int] = None
        self._current_temp: Optional[int] = None

    def get_mode(self) -> Optional[str]:
        """
        Gets mode from thermostat
        """
        return self._mode

    def get_fan_mode(self) -> Optional[str]:
        """
        Gets fan mode from thermostat
        """
        return self._fan_mode

    def get_operating_state(self) -> Optional[str]:
        """
        Gets operating state from thermostat
        """
        return self._operating_state

    def get_cooling_setpoint(self) -> Optional[int]:
        """
        Gets cooling setpoint from thermostat
        """
        return self._cooling_setpoint

    def get_heating_setpoint(self) -> Optional[int]:
        """
        Gets heating setpoint from thermostat
        """
        return self._heating_setpoint

    def get_current_humidity(self) -> Optional[int]:
        """
        Gets current humidity from thermostat
        """
        return self._current_humidity

    def get_current_temp(self) -> Optional[int]:
        """
        Gets current temperature from thermostat
        """
        return self._current_temp

    async def async_set_heating_setpoint(self, value: int):
        """
        Sets heating setpoint

        ``value`` str or int representing temperature to set
        """
        await self._client._async_send_command(
            self, attribute_name="heating_setpoint", value=str(value)
        )

        self._heating_setpoint = int(value)

    async def async_set_cooling_setpoint(self, value: int):
        """
        Sets cooling setpoint

        ``value`` str or int representing temperature to set
        """
        await self._client._async_send_command(
            self, attribute_name="cooling_setpoint", value=str(value)
        )

        self._cooling_setpoint = int(value)

    async def async_set_mode(self, mode: str):
        """
        Sets thermostat mode

        ``mode`` str. One of ``['aux_heat', 'heat', 'cool', 'auto', 'off']``
        """
        accepted_modes = ["aux_heat", "heat", "cool", "auto", "off"]

        if mode not in accepted_modes:
            raise ValueError(f"{mode} not in {accepted_modes}")

        await self._client._async_send_command(self, attribute_name="mode", value=mode)

        self._mode = mode

    async def async_set_fan_mode(self, fan_mode: str):
        """
        Sets thermostat fan mode

        ``value`` str. One of ``['auto', 'on']``
        """
        accepted_fan_modes = ["on", "auto"]

        if fan_mode not in accepted_fan_modes:
            raise ValueError(f"{fan_mode} not in {accepted_fan_modes}")

        await self._client._async_send_command(
            self,
            attribute_name="fan_mode",
            value=fan_mode,
        )

        self._fan_mode = fan_mode

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

        self._current_temp = float_to_int(attrs.get("current_temp"))

        self._cooling_setpoint = float_to_int(attrs.get("cooling_setpoint"))
        self._heating_setpoint = float_to_int(attrs.get("heating_setpoint"))

        temp_humidity = float_to_int(attrs.get("current_humidity"))
        if temp_humidity:
            self._current_humidity = (
                temp_humidity if temp_humidity > 0 else self._current_humidity
            )

        self._mode = attrs["mode"]
        self._fan_mode = attrs.get("fan_mode")
        self._operating_state = attrs.get("operating_state")

    def _update_parser(self, event: dict) -> None:
        """
        Called when ``Client._async_update_state`` returns info

        ``event`` dict passed in from ``Client._async_update_state``
        """
        _LOGGER.info("Updating Thermostat")
        last_read_state = str(event.get("last_read_state"))

        if event.get("name") == "current_humidity":
            self._current_humidity = (
                int(float(last_read_state))
                if int(float(last_read_state)) > 0
                else self._current_humidity
            )

        elif event.get("name") == "current_temp":
            self._current_temp = int(float(last_read_state))

        elif event.get("name") == "heating_setpoint":
            self._heating_setpoint = int(float(last_read_state))

        elif event.get("name") == "cooling_setpoint":
            self._cooling_setpoint = int(float(last_read_state))

        elif event.get("name") == "mode":
            self._mode = last_read_state

        elif event.get("name") == "fan_mode":
            self._fan_mode = last_read_state

        elif event.get("name") == "operating_state":
            self._operating_state = last_read_state
