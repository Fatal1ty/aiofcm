from uuid import uuid4


class NotificationRequest:
    __slots__ = ('device_token', 'message', 'notification_id', 'time_to_live', 'data', 'priority')

    def __init__(self, device_token, message=None, data=None, notification_id=None,
                 time_to_live=None, priority=None):
        self.device_token = device_token
        self.message = message
        self.notification_id = notification_id or str(uuid4())
        self.time_to_live = time_to_live
        self.data = data
        self.priority = priority

    def as_dict(self):
        result = dict(
            message_id=self.notification_id,
            to=self.device_token,
        )

        if self.message is not None:
            result['notification'] = self.message

        for field in ['data', 'priority', 'time_to_live']:
            value = getattr(self, field, None)
            if value is not None:
                result[field] = value

        return result


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
