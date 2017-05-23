from aiofcm.connection import FCMConnectionPool
from aiofcm.logging import logger


class FCM:
    def __init__(self, sender_id, api_key, max_connections=10, loop=None):
        self.pool = FCMConnectionPool(sender_id, api_key, max_connections, loop)

    async def send_notification(self, request):
        response = await self.pool.send_notification(request)
        if not response.is_successful:
            msg = 'Status of notification %s is %s' %\
                  (request.notification_id, response.status.upper())
            if response.description:
                msg += ' (%s)' % response.description
            logger.error(msg)
        return response
