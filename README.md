# SmartRent API
Unnoficial api for SmartRent devices

Uses websockets for communication and supports async functions

## Known Devices supported
### Locks
* Yale YRD256

### Thermostats
* Honeywell T6 Pro (TH6320ZW2003)


# Usage

## Getting an API Object
In order to get an api object to interact with, you must login with the `async_login` function. This starts and handles a web session with SmartRent's webserver.

```python
import asyncio

from smartrent import async_login

async def main():
    api = await async_login('<EMAIL>', '<PASSWORD>')

asyncio.run(main())
```

## Getting Devices
You can get lists of your devices from the api with the `get_locks` and `get_thermostats` functions. You can then interact with the devices with thier getter and setter functions.

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
