"""Project-level WebSocket consumers."""

from channels.generic.websocket import WebsocketConsumer

# Close code for a socket path no route serves. 4000-4999 are application
# codes (RFC 6455 §7.4.2); 4404 mirrors HTTP 404.
DENY_CLOSE_CODE = 4404


class DenyConsumer(WebsocketConsumer):
    """Refuse a /ws/ path that no real route matched, without accepting it.

    ``URLRouter`` raises ``ValueError`` for an unmatched path, which turns every
    scanner probe into a 500 and a logged traceback. This catch-all closes the
    handshake cleanly instead. It must stay the LAST route.
    """

    def connect(self):
        self.close(code=DENY_CLOSE_CODE)
