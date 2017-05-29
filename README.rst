aiofcm - An efficient Firebase Cloud Messaging Client Library for Python/asyncio
=================================================================================

.. image:: https://travis-ci.org/Fatal1ty/aiofcm.svg?branch=master
    :target: https://travis-ci.org/Fatal1ty/aiofcm

.. image:: https://img.shields.io/pypi/v/aiofcm.svg
    :target: https://pypi.python.org/pypi/aiofcm

.. image:: https://img.shields.io/pypi/pyversions/aiofcm.svg
    :target: https://pypi.python.org/pypi/aiofcm/

.. image:: https://img.shields.io/badge/License-Apache%202.0-blue.svg
    :target: https://opensource.org/licenses/Apache-2.0

**aiofcm** is a library designed specifically for sending messages such as push-notifications
to Android devices via Firebase Cloud Messaging platform. aiofcm provides an efficient client
through asynchronous XMPP protocol for use with Python's ``asyncio``
framework.

aiofcm requires Python 3.5 or later.


Performance
-----------

In my testing aiofcm allows you to send on average 1k messages per second on a single core.


Features
--------

* Internal connection pool which adapts to the current load
* Sending notification and/or data messages
* Ability to set TTL (time to live) for messages
* Ability to set priority for messages
* Ability to set collapse-key for messages


Installation
------------

Use pip to install::

    $ pip install aiofcm


Basic Usage
-----------

.. code-block:: python

    from uuid import uuid4
    from aiofcm import FCM, Message, PRIORITY_HIGH


    async def run():
        fcm = FCM('<NUMERICAL_SENDER_ID>', '<API_KEY>')
        message = Message(
            device_token='<DEVICE_TOKEN>',
            notification={           # optional
                "title": "Hello from Firebase",
                "body": "This is notification",
                "sound": "default"
            },
            data={"score": "3x1"},   # optional
            message_id=str(uuid4())  # optional
            time_to_live=3,          # optional
            priority=PRIORITY_HIGH,  # optional
        )
        await fcm.send_message(message)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())


License
-------

aiofcm is developed and distributed under the Apache 2.0 license.
