Introduction
============

``smartrent.py`` is an unofficial api for SmartRent devices.

This library uses websockets for communication and supports async functions.

Installation
************

.. code-block:: bash

    pip install smartrent.py

Motivation
**********

SmartRent seems to be growing in popularity for getting apartments into the smart home ecosystem. Natively they do not provide a public (or at least documeted) API to use.

This limitation makes it difficult to add automations that communicate with SmartRent outside of the few services they natively partner with (AKA Google Home) or through thier own SmartRent apps.

So thats why this library exists!

Limitations
***********

* Could break at any time! Use at your own discretion.
* Right now, this library only supports Thermostats and DoorLocks
* Currently this library has no support for sensors. I am hesistant to get my leak sensor wet to see what kind of data it returns.
* NO 2FA support! Only works with SmartRent accounts that have `email` and `password` auth!