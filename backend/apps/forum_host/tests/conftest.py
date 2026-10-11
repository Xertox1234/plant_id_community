"""Shared fixtures for the forum host's tests."""

import socket
import threading
import time

import pytest

# How often a waiting ``accept()`` wakes to check whether the test is over.
_ACCEPT_POLL_SECONDS = 0.05


class DripServer:
    """A loopback server that answers its first client with ``prefix``, then
    drips a byte every 50 ms for 3 s.

    ``stop()`` ends it promptly whether or not anything connected (todo 545
    item 2): ``accept()`` polls a stop event instead of relying on another
    thread's ``close()`` to wake it, which Linux never does, so a test whose
    fetch aborted before connecting no longer stalls teardown for the whole
    join. A client that resets the connection ends the thread quietly rather
    than raising in it."""

    def __init__(self, prefix):
        self.prefix = prefix
        self._stop = threading.Event()
        self._server = socket.create_server(("127.0.0.1", 0))
        self._server.settimeout(_ACCEPT_POLL_SECONDS)
        self.port = self._server.getsockname()[1]
        self.thread = threading.Thread(target=self._drip, daemon=True)
        self.thread.start()

    def _accept(self):
        while not self._stop.is_set():
            try:
                connection, _ = self._server.accept()
            except TimeoutError:
                continue
            except OSError:  # the listener was closed
                return None
            # The accepted socket inherits the listener's poll timeout.
            connection.settimeout(None)
            return connection
        return None

    def _drip(self):
        connection = self._accept()
        if connection is None:
            return
        with connection:
            try:
                connection.recv(4096)
                connection.sendall(self.prefix)
                for _ in range(60):
                    if self._stop.is_set():
                        return
                    connection.sendall(b"X")
                    time.sleep(0.05)
            except OSError:  # the client hung up or reset
                return

    def stop(self, timeout=5):
        self._stop.set()
        self.thread.join(timeout)
        self._server.close()


@pytest.fixture
def loopback_drip():
    """``loopback_drip(prefix) -> port``: start a ``DripServer``. Every
    server is stopped and its thread joined when the test ends (todo 539
    item 7; this was a helper the page tests imported from the image
    tests' module)."""
    started = []

    def start(prefix):
        server = DripServer(prefix)
        started.append(server)
        return server.port

    yield start
    for server in started:
        server.stop()
