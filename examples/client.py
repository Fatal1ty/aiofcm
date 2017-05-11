import asyncio
import logging

import uvloop

from aiofcm import FCM, NotificationRequest


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

    message = {
        "title": "Hello from Firebase",
        "body": "This is notification"
    }

    fcm = FCM(sender_id, api_key)

    async def send_request():
        request = NotificationRequest(
            device_token=device_token,
            message=message
        )
        await fcm.send_notification(request)

    async def main():
        await send_request()
        send_requests = [send_request() for _ in range(1000)]
        import time
        t = time.time()
        await asyncio.wait(send_requests)
        print('Done: %s' % (time.time() - t))
        print()
    try:
        loop = asyncio.get_event_loop()
        asyncio.ensure_future(main())
        loop.run_forever()
    except KeyboardInterrupt:
        pass
