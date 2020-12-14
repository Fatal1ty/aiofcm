import datetime
import time
import sys
import asyncio
from uuid import uuid4
from aiofcm import FCM, Message, PRIORITY_HIGH

# Send and receive firebase messages from cloud to device
# This example:
# 1. Sends a timestamp every 5 seconds to a subscribed device
# 2. Echo back an uppercase of the 'txt' field in the data


API_KEY = ... #String
SENDER_ID = ... #Integer

DEVICE_TOKEN = None


async def my_callback(device_token, app_name, data):
    global DEVICE_TOKEN

    print("=======================")
    print("Received:", data)
    print("=======================")

    txt = data['txt']
    txt = txt.upper() #Echo back uppercase txt field

    message = Message(
        device_token=device_token,
        data={"txt":txt},
        message_id=str(uuid4()), # optional
        time_to_live=0,          # optional
        priority=PRIORITY_HIGH,  # optional
    )

    await fcm.send_message(message)

    if txt == "subscribe".upper():
        DEVICE_TOKEN = device_token
        print("set DEVICE_TOKEN to", device_token)
    elif txt == "unsubscribe".upper():
        DEVICE_TOKEN = None
        print("unset DEVICE_TOKEN")


async def run():
    while True:
        if DEVICE_TOKEN is not None:
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
        await asyncio.sleep(5)


fcm = FCM(SENDER_ID, API_KEY, callback=my_callback)
loop = asyncio.get_event_loop()
asyncio.ensure_future(run())
loop.run_forever()
