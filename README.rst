aiofcm - An efficient Firebase Cloud Messaging Client Library for Python/asyncio
=================================================================================

.. image:: https://travis-ci.org/Fatal1ty/aiofcm.svg?branch=master
    :target: https://travis-ci.org/Fatal1ty/aiofcm

.. image:: https://img.shields.io/pypi/v/aiofcm.svg
    :target: https://pypi.python.org/pypi/aiofcm

**aiofcm** is a library designed specifically for sending push-notifications to Android devices
via Firebase Cloud Messaging platform. aiofcm provides an efficient client through
asynchronous XMPP protocol for use with Python's ``asyncio``
framework.

aiofcm requires Python 3.5 or later.


Performance
-----------

In my testing aiofcm allows you to send on average 1k notifications per second on a single core.


Features
--------

* Internal connection pool which adapts to the current load
* Ability to set TTL (time to live) for notifications


Installation
------------

Use pip to install::

    $ pip install aiofcm


Basic Usage
-----------

.. code-block:: python

    from uuid import uuid4
    from aiofcm import FCM, NotificationRequest


    async def run():
        fcm = FCM('<NUMERICAL_SENDER_ID>', '<API_KEY>')
        request = NotificationRequest(
            device_token='<DEVICE_TOKEN>',
            message={
                "title": "Hello from Firebase",
                "body": "This is notification",
            },
            notification_id=str(uuid4())  # optional
            time_to_live=3,               # optional
        )
        await fcm.send_notification(request)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())


License
-------

aiofcm is developed and distributed under the Apache 2.0 license.
