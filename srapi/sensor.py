from device import Device

class Sensor(Device):
    def __init__(self, email: str, password: str, device_id: str):
        super().__init__(email, password, device_id)
        "TODO"