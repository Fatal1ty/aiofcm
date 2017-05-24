import asyncio
import logging

import uvloop

from aiofcm import FCM, Message


def setup_logger(log_level):
    log_level = getattr(logging, log_level)
    logging.basicConfig(
        format='[%(asctime)s] %(levelname)8s %(module)6s:%(lineno)03d %(message)s',
        level=log_level
    )


if __name__ == '__main__':
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    setup_logger('DEBUG')

    device_token = '<DEVICE_TOKEN>'
    sender_id = '<NUMERICAL_SENDER_ID>'
    api_key = '<API_KEY>'

    notification = {
        "title": "Hello from Firebase",
        "body": "This is notification",
        "sound": "default"
    }

    fcm = FCM(sender_id, api_key)

    async def send_message():
        message = Message(
            device_token=device_token,
            notification=notification,
        )
        await fcm.send_message(message)

    async def main():
        send_messages = [send_message() for _ in range(1000)]
        import time
        t = time.time()
        await asyncio.wait(send_messages)
        print('Done: %s' % (time.time() - t))
        print()
    try:
        loop = asyncio.get_event_loop()
        asyncio.ensure_future(main())
        loop.run_forever()
    except KeyboardInterrupt:
        pass
