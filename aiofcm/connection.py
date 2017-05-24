import json
import asyncio

import aioxmpp
import aioxmpp.connector
import aioxmpp.xso
import OpenSSL

from aiofcm.logging import logger
from aiofcm.common import MessageResponse, STATUS_SUCCESS
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

    def __init__(self, sender_id, api_key, loop=None, max_requests=1000,
                 on_connection_lost=None):
        self.max_requests = max_requests
        self.xmpp_client = aioxmpp.Client(
            local_jid=aioxmpp.JID.fromstr('%s@gcm.googleapis.com' % sender_id),
            security_layer=aioxmpp.make_security_layer(api_key),
            override_peer=[
                (self.FCM_HOST, self.FCM_PORT,
                 aioxmpp.connector.XMPPOverTLSConnector())
            ],
            loop=loop
        )
        self.loop = loop
        self.on_connection_lost = on_connection_lost
        self._wait_connection = asyncio.Future()
        self.inactivity_timer = None

        self.requests = {}

    async def connect(self):
        self.xmpp_client.on_stream_established.connect(
            lambda: self._wait_connection.set_result(True)
        )
        self.xmpp_client.on_stream_destroyed.connect(
            self._on_stream_destroyed
        )
        self.xmpp_client.start()

        await self._wait_connection
        self.xmpp_client.stream.register_message_callback(
            type_=aioxmpp.MessageType.NORMAL,
            from_=None,
            cb=self.on_response
        )
        self.refresh_inactivity_timer()

    def close(self):
        if self.inactivity_timer:
            self.inactivity_timer.cancel()
        logger.debug('Closing connection %s', self)
        self.xmpp_client.stop()

    def _on_stream_destroyed(self, reason=None):
        reason = reason or ConnectionClosed()
        logger.debug('Stream of %s destroyed: %s', self, reason)
        self.xmpp_client.stop()

        if self.inactivity_timer:
            self.inactivity_timer.cancel()

        if self.on_connection_lost:
            self.on_connection_lost(self)

        for request in self.requests.values():
            if not request.done():
                request.set_exception(reason)

    def on_response(self, message):
        self.refresh_inactivity_timer()

        body = json.loads(message.fcm_payload.text)

        try:
            message_id = body['message_id']
            message_type = body['message_type']
        except KeyError:
            logger.warning('Got strange response: %s', body)
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
        except:
            self.requests.pop(message.message_id)
            raise

        response = await future_response
        return response

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

    def __init__(self, sender_id, api_key, max_connections=10, loop=None):
        self.sender_id = sender_id
        self.api_key = api_key
        self.max_connections = max_connections
        self.loop = loop or asyncio.get_event_loop()
        self.connections = []
        self._lock = asyncio.Lock()

        self.loop.set_exception_handler(self.exception_handler)

    async def connect(self):
        connection = FCMXMPPConnection(
            sender_id=self.sender_id,
            api_key=self.api_key,
            loop=self.loop,
            on_connection_lost=self.discard_connection
        )
        await connection.connect()
        logger.info('Connection established (total: %d)',
                    len(self.connections) + 1)
        return connection

    async def create_connection(self):
        connection = await self.connect()
        self.connections.append(connection)

    def discard_connection(self, connection):
        logger.debug('Connection %s discarded', connection)
        self.connections.remove(connection)
        logger.info('Connection released (total: %d)',
                    len(self.connections))

    async def acquire(self):
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
                connection = await self.connect()
                self.connections.append(connection)
                self._lock.release()
                return connection
            else:
                self._lock.release()
                logger.warning('Pool is busy, wait...')
                while True:
                    await asyncio.sleep(0.01)
                    for connection in self.connections:
                        if not connection.is_busy:
                            return connection

    async def send_message(self, message):
        attempt = 0
        while True:
            attempt += 1
            if attempt > self.MAX_ATTEMPTS:
                logger.warning('Trying to send message %s: attempt #%s',
                               message.message_id, attempt)
            logger.debug('Message %s: waiting for connection',
                         message.message_id)
            connection = await self.acquire()
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

    def exception_handler(self, _, context):
        exc = context.get('exception')
        # See https://github.com/horazont/aioopenssl/issues/2
        if not isinstance(exc, OpenSSL.SSL.SysCallError):
            logger.exception(exc)
