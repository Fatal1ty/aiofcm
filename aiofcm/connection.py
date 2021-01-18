import json
import asyncio
from typing import Optional, NoReturn

import aioxmpp
import aioxmpp.connector
import aioxmpp.xso
import OpenSSL

from aiofcm.logging import logger
from aiofcm.common import Message, MessageResponse, STATUS_SUCCESS
from aiofcm.exceptions import ConnectionClosed


class FCMMessage(aioxmpp.xso.XSO):
    TAG = ('google:mobile:data', 'gcm')
    text = aioxmpp.xso.Text(default=None)


aioxmpp.stanza.Message.fcm_payload = aioxmpp.xso.Child([FCMMessage])


class FCMMessageType:
    ACK = 'ack'
    NACK = 'nack'


class FCMXMPPConnection:
    FCM_HOST = 'fcm-xmpp.googleapis.com'
    FCM_PORT = 5235
    INACTIVITY_TIME = 10

    def __init__(self, sender_id, api_key, upstream_callback=None, loop=None,
                 max_requests=1000):
        self.upstream_callback = upstream_callback
        self.max_requests = max_requests
        self.xmpp_client = self._create_client(sender_id, api_key, loop)
        self.loop = loop
        self._wait_connection = asyncio.Future()
        self.inactivity_timer = None
        self.stream_destroyed = False

        self.requests = {}

    def _create_client(self, sender_id, api_key, loop=None) -> aioxmpp.Client:
        xmpp_client = aioxmpp.Client(
            local_jid=aioxmpp.JID.fromstr('%s@gcm.googleapis.com' % sender_id),
            security_layer=aioxmpp.make_security_layer(api_key),
            override_peer=[
                (self.FCM_HOST, self.FCM_PORT,
                 aioxmpp.connector.XMPPOverTLSConnector())
            ],
            loop=loop
        )
        xmpp_client.on_stream_established.connect(
            lambda: self._wait_connection.set_result(True)
        )
        xmpp_client.on_stream_destroyed.connect(
            self._on_stream_destroyed
        )
        xmpp_client.on_failure.connect(
            lambda exc: self._wait_connection.set_exception(exc)
        )
        xmpp_client.stream.register_message_callback(
            type_=aioxmpp.MessageType.NORMAL,
            from_=None,
            cb=self.on_response
        )
        return xmpp_client

    @property
    def connected(self):
        return self.xmpp_client.running

    async def connect(self):
        self.xmpp_client.start()
        await self._wait_connection
        self.refresh_inactivity_timer()

    def close(self):
        if self.inactivity_timer:
            self.inactivity_timer.cancel()
        logger.debug('Closing connection %s', self)
        self.xmpp_client.stop()

    def _on_stream_destroyed(self, reason=None):
        reason = reason or ConnectionClosed()
        logger.debug('Stream of %s was destroyed: %s', self, reason)
        self.xmpp_client.stop()

        if self.inactivity_timer:
            self.inactivity_timer.cancel()

        for request in self.requests.values():
            if not request.done():
                request.set_exception(reason)

        self.stream_destroyed = True

    def on_response(self, message):
        self.refresh_inactivity_timer()

        body = json.loads(message.fcm_payload.text)

        handle_upstream = False
        try:
            message_id = body['message_id']
            message_type = body['message_type']
        except KeyError:
            try:
                message_id = body['message_id']
                category = body['category']
                device_token = body['from']
                data = body['data']
                handle_upstream = True
            except KeyError:
                logger.warning('Got strange response: %s', body)
                return

        if handle_upstream:
            asyncio.ensure_future(self.send_ack(device_token, message_id))
            if self.upstream_callback is not None:
                asyncio.ensure_future(self.upstream_callback(device_token,
                                                             category, data))
            return

        if message_type not in (FCMMessageType.ACK, FCMMessageType.NACK):
            return

        request = self.requests.pop(message_id, None)
        if not request:
            logger.warning('Got response for unknown message %s', message_id)
            return

        if message_type == FCMMessageType.ACK:
            result = MessageResponse(message_id, STATUS_SUCCESS)
            request.set_result(result)
        elif message_type == FCMMessageType.NACK:
            status = body['error']
            description = body['error_description']
            result = MessageResponse(message_id, status, description)
            request.set_result(result)

    async def send_message(self, message):
        if not self.connected:
            await self.connect()
        msg = aioxmpp.Message(
            type_=aioxmpp.MessageType.NORMAL
        )
        payload = FCMMessage()

        payload_body = message.as_dict()

        payload.text = json.dumps(payload_body)
        msg.fcm_payload = payload

        future_response = asyncio.Future()
        self.requests[message.message_id] = future_response

        self.refresh_inactivity_timer()
        try:
            await self.xmpp_client.stream.send(msg)
        except Exception:
            self.requests.pop(message.message_id)
            raise

        response = await future_response
        return response

    async def send_ack(self, device_token, message_id):
        if not self.connected:
            await self.connect()
        msg = aioxmpp.Message(
            type_=aioxmpp.MessageType.NORMAL
        )
        payload = FCMMessage()

        payload_body = {"to": str(device_token),
                        "message_id": str(message_id),
                        "message_type": "ack"}

        payload.text = json.dumps(payload_body)
        msg.fcm_payload = payload

        self.refresh_inactivity_timer()
        await self.xmpp_client.stream.send(msg)

    def refresh_inactivity_timer(self):
        if self.inactivity_timer:
            self.inactivity_timer.cancel()
        self.inactivity_timer = self.loop.call_later(
            self.INACTIVITY_TIME, self.close)

    @property
    def is_busy(self):
        return len(self.requests) >= self.max_requests


class FCMConnectionPool:
    MAX_ATTEMPTS = 10

    def __init__(self, sender_id, api_key, upstream_callback=None,
                 min_connections=0, max_connections=10, loop=None):
        # type: (int, str, callback, int, int,
        #        Optional[asyncio.AbstractEventLoop]) -> NoReturn
        self.sender_id = sender_id
        self.api_key = api_key
        self.upstream_callback = upstream_callback
        if min_connections > max_connections:
            raise ValueError("min_connections is greater than max_connections")
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.loop = loop or asyncio.get_event_loop()
        self.connections = []
        self._lock = asyncio.Lock(loop=self.loop)

        self.loop.set_exception_handler(self.__exception_handler)

        if min_connections == 0:
            self.maintain_connections_task = None
        else:
            self.maintain_connections_task = asyncio.ensure_future(self.maintain_min_connections_open())

    async def connect(self) -> FCMXMPPConnection:
        connection = FCMXMPPConnection(
            sender_id=self.sender_id,
            api_key=self.api_key,
            upstream_callback=self.upstream_callback,
            loop=self.loop,
        )
        await connection.connect()
        logger.info('Connection established (total: %d)',
                    len(self.connections) + 1)
        return connection

    def close(self):
        if self.maintain_connections_task:
            self.maintain_connections_task.cancel()
        self.maintain_connections_task = None
        for connection in self.connections:
            connection.close()

    async def create_connection(self):
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
                    logger.error('Could not connect to server: %s', e)
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
        attempt = 0
        while True:
            attempt += 1
            if attempt > self.MAX_ATTEMPTS:
                logger.warning('Trying to send message %s: attempt #%s',
                               message.message_id, attempt)
            logger.debug('Message %s: waiting for connection',
                         message.message_id)
            try:
                connection = await self.acquire()
            except ConnectionError:
                logger.warning('Could not send notification %s due to '
                               'connection problem', message.message_id)
                await asyncio.sleep(1)
                continue
            logger.debug('Message %s: connection %s acquired',
                         message.message_id, connection)
            try:
                response = await connection.send_message(message)
                return response
            except ConnectionClosed:
                logger.warning('Could not send message %s: '
                               'ConnectionClosed', message.message_id)
            except Exception as e:
                logger.error('Could not send message %s: %s',
                             message.message_id, e)

    async def maintain_min_connections_open(self):
        while self.maintain_connections_task:
            self.connections = [connection for connection in self.connections if not connection.stream_destroyed]

            missing_connections = max(0, self.min_connections
                                      - len(self.connections))
            if missing_connections > 0:
                logger.debug('Creating %d missing connections',
                             missing_connections)
                for _ in range(missing_connections):
                    asyncio.ensure_future(self.acquire())

            await asyncio.sleep(1)

            if self.maintain_connections_task:
                for connection in self.connections[-missing_connections:]:
                    connection.refresh_inactivity_timer()

    @staticmethod
    def __exception_handler(_, context):
        exc = context.get('exception')
        if not isinstance(exc, OpenSSL.SSL.SysCallError):
            logger.exception(exc)
