from uuid import uuid4


class NotificationRequest:
    __slots__ = ('device_token', 'message', 'notification_id', 'time_to_live')

    def __init__(self, device_token, message, notification_id=None,
                 time_to_live=None):
        self.device_token = device_token
        self.message = message
        self.notification_id = notification_id or str(uuid4())
        self.time_to_live = time_to_live


class NotificationResult:
    __slots__ = ('notification_id', 'status', 'description')

    def __init__(self, notification_id, status, description=None):
        self.notification_id = notification_id
        self.status = status
        self.description = description

    @property
    def is_successful(self):
        return self.status == NotificationStatus.SUCCESS


class NotificationStatus:
    SUCCESS = 'SUCCESS'
