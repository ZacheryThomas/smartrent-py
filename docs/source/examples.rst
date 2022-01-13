Examples
========

Installation/Usage:
*******************

.. code-block:: bash

    pip install smartrent


Quickstart:
***********

This library makes heavy use of ``async`` functions. For those who are unfamiliar with them, they can take a while to get used to. But for now we can just set up a quick ``main`` method and call it with ``asyncio.run(main())``

The quickest way to get started playing with devices is through the :meth:`smartrent.async_login` function. This starts and handles a web session with SmartRent's http webserver as well as initally gets all the info for the devices in your account.

We have to call :meth:`smartrent.async_login` with the ``await`` keyword in order for the ``async`` function to run and return a value.

Once we run that function, we can then call ``api.get_locks()`` or ``api.get_thermostats()`` to return a list of :class:`smartrent.lock.DoorLock` or :class:`smartrent.thermostat.Thermostat` objects.

.. code-block:: bash

    import asyncio
    from smartrent import async_login

    async def main():
        api = await async_login('<EMAIL>', '<PASSWORD>')

        print(api.get_locks())

    asyncio.run(main())


Changing the state of a DoorLock:
*********************************

This code gets the first :class:`smartrent.lock.DoorLock` we find through the api, locks it, waits 10 seconds, and then unlocks it

.. code-block:: bash

    import asyncio
    from smartrent import async_login

    async def main():
        api = await async_login('<EMAIL>', '<PASSWORD>')

        locks = api.get_locks()

        first_lock = locks[0]

        await first_lock.async_set_locked(False)

        asyncio.sleep(10)

        await first_lock.async_set_locked(True)

    asyncio.run(main())
