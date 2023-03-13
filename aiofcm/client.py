import asyncio
from typing import Optional

from aiofcm.connection import FCMConnectionPool
from aiofcm.common import Message, MessageResponse
from aiofcm.logging import logger


class FCM:
    def __init__(
        self,
        sender_id: int,
        api_key: str,
        max_connections: int = 10,
        max_connection_attempts: Optional[int] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ):
        self.pool = FCMConnectionPool(
            sender_id=sender_id,
            api_key=api_key,
            max_connections=max_connections,
            max_connection_attempts=max_connection_attempts,
            loop=loop,
        )

    async def send_message(self, message: Message) -> MessageResponse:
        response = await self.pool.send_message(message)
        if not response.is_successful:
            msg = "Status of message %s is %s" % (
                message.message_id,
                response.status,
            )
            if response.description:
                msg += " (%s)" % response.description
            logger.error(msg)
        return response
