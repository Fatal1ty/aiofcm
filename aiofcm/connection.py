import sys
import json
import asyncio
from asyncio import Future
from typing import Optional, Dict, List

import aioxmpp
import aioxmpp.connector
import aioxmpp.xso
import OpenSSL

from aiofcm.logging import logger
from aiofcm.common import Message, MessageResponse, STATUS_SUCCESS
from aiofcm.exceptions import ConnectionClosed, ConnectionError


class FCMMessage(aioxmpp.xso.XSO):
    TAG = ("google:mobile:data", "gcm")
    text = aioxmpp.xso.Text(default=None)


aioxmpp.stanza.Message.fcm_payload = aioxmpp.xso.Child([FCMMessage])


class FCMMessageType:
    ACK = "ack"
    NACK = "nack"


class FCMXMPPConnection:
    FCM_HOST = "fcm-xmpp.googleapis.com"
    FCM_PORT = 5235
    INACTIVITY_TIME = 10

    def __init__(
        self,
        sender_id: int,
        api_key: str,
        loop: asyncio.AbstractEventLoop,
        max_requests: int = 1000,
    ):
        self.max_requests = max_requests
        self.xmpp_client = self._create_client(sender_id, api_key, loop)
        self.loop = loop
        self._wait_connection: Future = Future()
        self.inactivity_timer: Optional[asyncio.TimerHandle] = None

        self.requests: Dict[str, Future] = {}

    def _create_client(
        self,
        sender_id: int,
        api_key: str,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> aioxmpp.Client:
        xmpp_client = aioxmpp.Client(
            local_jid=aioxmpp.JID.fromstr("%s@gcm.googleapis.com" % sender_id),
            security_layer=aioxmpp.make_security_layer(api_key),
            override_peer=[
                (
                    self.FCM_HOST,
                    self.FCM_PORT,
                    aioxmpp.connector.XMPPOverTLSConnector(),
                )
            ],
            loop=loop,
        )
        xmpp_client.on_stream_established.connect(
            lambda: self._wait_connection.set_result(True)
        )
        xmpp_client.on_stream_destroyed.connect(self._on_stream_destroyed)
        xmpp_client.on_failure.connect(
            lambda exc: self._wait_connection.set_exception(exc)
        )
        xmpp_client.stream.register_message_callback(
            type_=aioxmpp.MessageType.NORMAL, from_=None, cb=self.on_response
        )
        return xmpp_client

    @property
    def connected(self) -> bool:
        return self.xmpp_client.running

    async def connect(self) -> None:
        self.xmpp_client.start()
        await self._wait_connection
        self.refresh_inactivity_timer()

    def close(self) -> None:
        if self.inactivity_timer:
            self.inactivity_timer.cancel()
        logger.debug("Closing connection %s", self)
        self.xmpp_client.stop()

    def _on_stream_destroyed(self, reason: Optional[Exception] = None) -> None:
        reason = reason or ConnectionClosed()
        logger.debug("Stream of %s was destroyed: %s", self, reason)
        self.xmpp_client.stop()

        if self.inactivity_timer:
            self.inactivity_timer.cancel()

        for request in self.requests.values():
            if not request.done():
                request.set_exception(reason)

    def on_response(self, message: aioxmpp.stanza.Message) -> None:
        self.refresh_inactivity_timer()

        body = json.loads(message.fcm_payload.text)  # type: ignore

        try:
            message_id = body["message_id"]
            message_type = body["message_type"]
        except KeyError:
            logger.warning("Got strange response: %s", body)
            return

        if message_type not in (FCMMessageType.ACK, FCMMessageType.NACK):
            return

        request = self.requests.pop(message_id, None)
        if not request:
            logger.warning("Got response for unknown message %s", message_id)
            return

        if message_type == FCMMessageType.ACK:
            result = MessageResponse(message_id, STATUS_SUCCESS)
            request.set_result(result)
        elif message_type == FCMMessageType.NACK:
            status = body["error"]
            description = body["error_description"]
            result = MessageResponse(message_id, status, description)
            request.set_result(result)

    async def send_message(self, message: Message) -> MessageResponse:
        if not self.connected:
            await self.connect()
        msg = aioxmpp.Message(type_=aioxmpp.MessageType.NORMAL)
        payload = FCMMessage()

        payload_body = message.as_dict()

        payload.text = json.dumps(payload_body)
        msg.fcm_payload = payload

        future_response: Future = asyncio.Future()
        self.requests[message.message_id] = future_response

        self.refresh_inactivity_timer()
        try:
            await self.xmpp_client.stream.send(msg)
        except Exception:
            self.requests.pop(message.message_id)
            raise

        response = await future_response
        return response

    def refresh_inactivity_timer(self) -> None:
        if self.inactivity_timer:
            self.inactivity_timer.cancel()
        self.inactivity_timer = self.loop.call_later(
            self.INACTIVITY_TIME, self.close
        )

    @property
    def is_busy(self) -> bool:
        return len(self.requests) >= self.max_requests


class FCMConnectionPool:
    def __init__(
        self,
        sender_id: int,
        api_key: str,
        max_connections: int = 10,
        max_connection_attempts: Optional[int] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ):
        self.sender_id = sender_id
        self.api_key = api_key
        self.max_connections = max_connections
        self.max_connection_attempts = max_connection_attempts
        self.loop = loop or asyncio.get_event_loop()
        self.connections: List[FCMXMPPConnection] = []
        # Python 3.10+ does not use the "loop" parameter
        if sys.version_info >= (3, 10):
            self._lock = asyncio.Lock()
        else:
            self._lock = asyncio.Lock(loop=self.loop)

        self.loop.set_exception_handler(self.__exception_handler)

    async def connect(self) -> FCMXMPPConnection:
        connection = FCMXMPPConnection(
            sender_id=self.sender_id,
            api_key=self.api_key,
            loop=self.loop,
        )
        await connection.connect()
        logger.info(
            "Connection established (total: %d)", len(self.connections) + 1
        )
        return connection

    def close(self) -> None:
        for connection in self.connections:
            connection.close()

    async def create_connection(self) -> None:
        connection = await self.connect()
        self.connections.append(connection)

    async def acquire(self) -> FCMXMPPConnection:
        for connection in self.connections:
            if not connection.is_busy:
                return connection
        else:
            await self._lock.acquire()
            for connection in self.connections:
                if not connection.is_busy:
                    self._lock.release()
                    return connection
            if len(self.connections) < self.max_connections:
                try:
                    connection = await self.connect()
                except Exception as e:
                    logger.error("Could not connect to server: %s", e)
                    self._lock.release()
                    raise ConnectionError
                self.connections.append(connection)
                self._lock.release()
                return connection
            else:
                self._lock.release()
                while True:
                    await asyncio.sleep(0.01)
                    for connection in self.connections:
                        if not connection.is_busy:
                            return connection

    async def send_message(self, message: Message) -> MessageResponse:
        failed_attempts = 0
        while True:
            logger.debug(
                "Message %s: waiting for connection", message.message_id
            )
            try:
                connection = await self.acquire()
            except ConnectionError:
                failed_attempts += 1
                logger.warning(
                    "Could not send notification %s due to "
                    "connection problem",
                    message.message_id,
                )

                if (
                    self.max_connection_attempts is not None
                    and failed_attempts > self.max_connection_attempts
                ):
                    logger.error(
                        "Failed to connect after %d attempts.", failed_attempts
                    )
                    raise

                await asyncio.sleep(1)
                continue
            logger.debug(
                "Message %s: connection %s acquired",
                message.message_id,
                connection,
            )
            try:
                response = await connection.send_message(message)
                return response
            except ConnectionClosed:
                logger.warning(
                    "Could not send message %s: " "ConnectionClosed",
                    message.message_id,
                )
            except Exception as e:
                logger.error(
                    "Could not send message %s: %s", message.message_id, e
                )

    @staticmethod
    def __exception_handler(
        _: asyncio.AbstractEventLoop, context: Dict
    ) -> None:
        exc = context.get("exception")
        if not isinstance(exc, OpenSSL.SSL.SysCallError):  # type: ignore
            logger.exception(exc)
