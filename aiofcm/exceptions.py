class ConnectionClosed(Exception):
    pass

    def __str__(self) -> str:
        return "Connection closed"


class ConnectionError(Exception):
    def __str__(self) -> str:
        return "Failed to connect"
