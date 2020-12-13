import datetime
import time
import sys
import asyncio
from uuid import uuid4
from aiofcm import FCM, Message, PRIORITY_HIGH

# Send and receive firebase messages from cloud to device
# This example:
# 1. Sends a timestamp every 30 seconds to a specified device
# 2. Echo back an uppercase of the 'txt' field in the data


API_KEY = ...
DEVICE_TOKEN = ...
SENDER_ID = ...


async def my_callback(device_token, app_name, data):
    print("=======================")
    print("Received:", data)
    print("=======================")

    txt = data['txt']
    txt = txt.upper() #Echo back uppercase txt field

    message = Message(
        device_token=DEVICE_TOKEN,
        data={"txt":txt},
        message_id=str(uuid4()), # optional
        time_to_live=0,          # optional
        priority=PRIORITY_HIGH,  # optional
    )

    await fcm.send_message(message)


async def run():
    while True:
        txt = datetime.datetime.now().strftime("%H:%M:%S")

        message = Message(
            device_token=DEVICE_TOKEN,
            data={"txt":txt},
            message_id=str(uuid4()), # optional
            time_to_live=0,          # optional
            priority=PRIORITY_HIGH,  # optional
        )

        print(time.time(), "Send:", txt)
        await fcm.send_message(message)
        await asyncio.sleep(30)


fcm = FCM(SENDER_ID, API_KEY, callback=my_callback)
loop = asyncio.get_event_loop()
asyncio.ensure_future(run())
loop.run_forever()
