import asyncio
import os

import srapi

EMAIL = os.getenv('sr_email')
PASSWORD = os.getenv('sr_password')

if (not EMAIL) or (not PASSWORD):
    print('Email or Password env vars not defined!')
    exit(1)


async def main():
    smartrent = srapi.SmartRent(email=EMAIL, password=PASSWORD)

    thermostats = smartrent.get_thermostats()

    thermostat = thermostats[0]

    previous_temp = None
    while True:
        current_temp = thermostat.get_current_temp()

        if  previous_temp != current_temp:
            previous_temp = current_temp

            print('current_temp:', previous_temp)

        await asyncio.sleep(60)


asyncio.get_event_loop().run_until_complete(main())
