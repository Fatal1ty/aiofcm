from uuid import uuid4


PRIORITY_NORMAL = 'normal'
PRIORITY_HIGH = 'high'

STATUS_SUCCESS = 'SUCCESS'


class Message:
    __slots__ = ('device_token', 'notification', 'data', 'priority',
                 'message_id', 'time_to_live')

    def __init__(self, device_token, notification=None, data=None,
                 priority=None, message_id=None, time_to_live=None):
        self.device_token = device_token
        self.notification = notification
        self.data = data
        self.priority = priority
        self.message_id = message_id or str(uuid4())
        self.time_to_live = time_to_live


class MessageResponse:
    __slots__ = ('message_id', 'status', 'description')

    def __init__(self, message_id, status, description=None):
        self.message_id = message_id
        self.status = status
        self.description = description

    @property
    def is_successful(self):
        return self.status == STATUS_SUCCESS
