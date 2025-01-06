# SmartRent API

[![PyPI version][pypi-version-badge]](https://pypi.org/project/smartrent-py/)
[![Supported Python versions][supported-versions-badge]](https://pypi.org/project/smartrent-py/)
[![PyPI downloads monthly][m-downloads-badge]](https://pypistats.org/packages/smartrent-py)
[![GitHub License][license-badge]](LICENSE.txt)
[![Documentation Status][docs-badge]](https://smartrentpy.readthedocs.io/en/latest/?badge=latest)
[![Code style: black][black-badge]](https://github.com/psf/black)

`smartrent-py` is a simple library for SmartRent devices

Uses websockets for communication and supports async functions

Feel free to ⭐️ this repo to get notified about the latest features!

[📚 Read the docs! 📚](https://smartrentpy.readthedocs.io)
## Supported Devices
This client supports:
* 🔐 Door Locks
* 🌡 Thermostats
* 💧 Leak Sensors
* 🏃 Motion Sensors
* 💡 Binary Switches
* 🎚 Multilevel (Dimmer) Switches


## Usage

### Installation

```bash
pip install smartrent-py
```

### Getting an API Object
In order to get an api object to interact with, you must login with the `async_login` function. This starts and handles a web session with SmartRent.

```python
import asyncio

from smartrent import async_login

async def main():
    api = await async_login('<EMAIL>', '<PASSWORD>')

asyncio.run(main())
```

### Getting Devices
You can get lists of your devices from the api with the `get_locks`, `get_thermostats`, `get_switches` and `get_leak_sensors` functions. You can then interact with the devices with their getter and setter functions.

```python
import asyncio

from smartrent import async_login

async def main():
    api = await async_login('<EMAIL>', '<PASSWORD>')

    lock = api.get_locks()[0]
    locked = lock.get_locked()

    if not locked:
        await lock.async_set_locked(True)

asyncio.run(main())
```

### Automatic Updating
If you need to get live updates to your device object from SmartRent, you can do that by calling `start_updater`. You can stop getting updates by calling `stop_updater`.

You can also set a callback function via `set_update_callback` that will be called when an update is triggered.

For example, if you want to set your thermostat to `Dad Mode` you can trigger an event every time the `cooling_setpoint` is changed and just change it back to your own desired value.
```python
import asyncio

from smartrent import async_login

async def main():
    api = await async_login('<EMAIL>', '<PASSWORD>')

    thermo = api.get_thermostats()[0]
    thermo.start_updater()

    CONSTANT_COOL = 80

    async def on_evt():
        if CONSTANT_COOL != thermo.get_cooling_setpoint():
            await thermo.async_set_cooling_setpoint(CONSTANT_COOL)

    thermo.set_update_callback(on_evt)

    while True:
        await asyncio.sleep(60)

asyncio.run(main())
```

## Development
### Setting up dev enviornment

```
pip install -r requirements_test.txt
```

### Running the code formatter
[Black](https://github.com/psf/black) is used for quick and easy code formatting

```
black smartrent
```

## Special thanks
Much inspiration was taken from these projects:

[AMcPherran/SmartRent-MQTT-Bridge](https://github.com/AMcPherran/SmartRent-MQTT-Bridge)

[natanweinberger/smartrent-python](https://github.com/natanweinberger/smartrent-python)

[Burry/homebridge-smartrent](https://github.com/Burry/homebridge-smartrent)
## Versioning

We use [SemVer](http://semver.org/) for versioning. For the versions available, see the [tags on this repository](https://github.com/your/project/tags).

# Adding Unsupported Devices!

This library is built in a way that it is easy to add any smartrent device. If you find that one of the devices you own is not supported, we should be able to add it to this libray.

Two things are needed to get the info to add a new device:
* We have to get some device info from smartrents api
* We need to get info about how the device reacts when it enters different states

Both of these can be done in one script.

You have to run `python3 ./tools/device_helper.py`

It will print out some output and a table with `Device ID`s and `Device Names`. The device you wish to add should be listed in that table.
```
Device ID:      Device Name:
==============================
2211234         Thermostat
2212345         Front Door - Lock
2212347         Washer - Leak Sensor
```

The program will then ask for a `Device ID` that you wish to track. Enter in the `Device ID` you want to gather information from.

```
Put in the Device ID you wish to track: 2211234
Joining topic for 2211234...
{'response': {}, 'status': 'ok'}
```

You can now change the state of your device either physically in your apartment/house or through the SmartRent app. For example, this is a thermostat's cooling point being turned up, and then the thermostat sending an update about the current humidity
```
ThermostatSetpoint  cooling_setpoint    77
MultiLvlSensor      current_humidity    53
```

Once you get a good amount of info, open up an issue describing that you wish to add support for a new device and paste all of the output from `device_helper.py`. Feel free to hide your `Device ID`s if you wish.


[pypi-version-badge]: https://img.shields.io/pypi/v/smartrent-py.svg?logo=pypi&logoColor=FFE873&style=for-the-badge
[supported-versions-badge]: https://img.shields.io/pypi/pyversions/smartrent-py.svg?logo=python&logoColor=FFE873&style=for-the-badge
[downloads-badge]: https://static.pepy.tech/personalized-badge/smartrent-py?period=total&units=international_system&left_color=grey&right_color=orange&left_text=total%20downloads&style=for-the-badge
[m-downloads-badge]: https://img.shields.io/pypi/dm/smartrent-py.svg?style=for-the-badge
[license-badge]: https://img.shields.io/github/license/ZacheryThomas/smartrent-py.svg?style=for-the-badge
[docs-badge]: https://readthedocs.org/projects/smartrentpy/badge/?version=latest&style=for-the-badge
[black-badge]: https://img.shields.io/badge/code%20style-black-000000.svg?style=for-the-badge
