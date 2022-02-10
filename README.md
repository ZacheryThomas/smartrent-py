# SmartRent API

[![PyPI version][pypi-version-badge]](https://pypi.org/project/smartrent-py/)
[![Supported Python versions][supported-versions-badge]](https://pypi.org/project/smartrent-py/)
[![PyPI downloads monthly][m-downloads-badge]](https://pypistats.org/packages/smartrent-py)
[![GitHub License][license-badge]](LICENSE.txt)
[![Documentation Status][docs-badge]](https://smartrentpy.readthedocs.io/en/latest/?badge=latest)
[![Code style: black][black-badge]](https://github.com/psf/black)

Unofficial api for SmartRent devices

Uses websockets for communication and supports async functions

[📚 Read the docs! 📚](https://smartrentpy.readthedocs.io)
## Known Devices supported
### Locks
* Yale YRD256

### Thermostats
* Honeywell T6 Pro (TH6320ZW2003)


# Usage

## Installing

```bash
pip install smartrent.py
```

## Getting an API Object
In order to get an api object to interact with, you must login with the `async_login` function. This starts and handles a web session with SmartRent.

```python
import asyncio

from smartrent import async_login

async def main():
    api = await async_login('<EMAIL>', '<PASSWORD>')

asyncio.run(main())
```

## Getting Devices
You can get lists of your devices from the api with the `get_locks` and `get_thermostats` functions. You can then interact with the devices with their getter and setter functions.

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

## Automatic Updating
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

# TODOs

* Add support for water sensors. I'm not brave enough to get my sensor wet and see what messages it provides
* Add support for Two Factor Auth

[pypi-version-badge]: https://img.shields.io/pypi/v/smartrent-py.svg?logo=pypi&logoColor=FFE873&style=for-the-badge
[supported-versions-badge]: https://img.shields.io/pypi/pyversions/smartrent-py.svg?logo=python&logoColor=FFE873&style=for-the-badge
[downloads-badge]: https://static.pepy.tech/personalized-badge/smartrent-py?period=total&units=international_system&left_color=grey&right_color=orange&left_text=total%20downloads&style=for-the-badge
[m-downloads-badge]: https://img.shields.io/pypi/dm/smartrent-py.svg?style=for-the-badge
[license-badge]: https://img.shields.io/github/license/ZacheryThomas/smartrent.py.svg?style=for-the-badge
[docs-badge]: https://readthedocs.org/projects/smartrentpy/badge/?version=latest&style=for-the-badge
[black-badge]: https://img.shields.io/badge/code%20style-black-000000.svg?style=for-the-badge
