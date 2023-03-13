class ConnectionClosed(Exception):
    pass

    def __str__(self):
        return 'Connection closed'


class ConnectionError(Exception):
    def __str__(self):
        return 'Failed to connect'
