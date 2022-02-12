Introduction
============

``smartrent.py`` is an unofficial api for SmartRent devices.

This library uses websockets for communication and supports async functions.

Motivation
**********

SmartRent seems to be growing in popularity for getting apartments into the smart home ecosystem. Natively they do not provide a public (or at least documeted) API to use.

This limitation makes it difficult to add automations that communicate with SmartRent outside of the few services they natively support, like Google Home, or through thier own SmartRent apps.

So thats why this library exists!

Limitations
***********

* Could break at any time! Use at your own discretion.
* NO 2FA support! Only works with SmartRent accounts that have `email` and `password` auth!
