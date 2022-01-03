import aiohttp

from .device import Device


class Sensor(Device):
    """
    Represents Sensor SmartRent device
    """

    def __init__(
        self,
        email: str,
        password: str,
        device_id: str,
        aiohttp_session: aiohttp.ClientSession = None,
    ):
        super().__init__(email, password, device_id, aiohttp_session)
        self._locked = None
        self._notification = None
