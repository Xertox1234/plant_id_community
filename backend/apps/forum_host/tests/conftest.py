"""Shared fixtures for the forum host's tests."""

import errno
import socket
import threading
import time

import pytest

# How often a waiting ``accept()`` or ``recv()`` wakes to check whether the
# test is over.
_ACCEPT_POLL_SECONDS = 0.05

# ``accept()`` errors that concern one client, not the listener (todo 550
# item 6): the drip server keeps listening after one of these.
_TRANSIENT_ACCEPT_ERRNOS = {errno.ECONNABORTED, errno.EINTR, errno.EAGAIN}


class DripServer:
    """A loopback server that answers its first client with ``prefix``, then
    drips a byte every 50 ms for 3 s.

    ``stop()`` ends it promptly whether or not anything connected, and
    whether or not a client that connected ever sent anything (todo 545
    item 2, todo 550 item 5): ``accept()`` and the first ``recv()`` poll a
    stop event instead of relying on another thread's ``close()`` to wake
    them, which Linux never does. A client that closes before sending
    anything, or resets before sending anything, gets nothing and leaves
    ``hung_up`` False (todo 598). A client that hangs up or resets mid-drip
    ends the thread quietly rather than raising in it; ``hung_up`` records
    that it did.

    ``accepted`` is set once a client is accepted, so a test can act on the
    connection knowing the server is past ``accept()`` (todo 611), and
    ``left_before_request`` records how a client that sent nothing left:
    ``"eof"`` or ``"reset"``."""

    def __init__(self, prefix):
        self.prefix = prefix
        self.hung_up = False
        self.accepted = threading.Event()
        self.left_before_request = None
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
            except OSError as error:
                if error.errno in _TRANSIENT_ACCEPT_ERRNOS:
                    continue  # one client's failure; keep listening
                return None  # the listener was closed
            # CPython gives an accepted socket the default timeout (None,
            # blocking), not the listener's: poll the first recv instead.
            connection.settimeout(_ACCEPT_POLL_SECONDS)
            self.accepted.set()
            return connection
        return None

    def _receive_request(self, connection):
        """The client's first bytes, or None when the test ended first or
        the client left without sending anything: a clean EOF (todo 576
        item 2) or a reset (todo 598) before any request is the client
        leaving, not a request to answer, and not a mid-drip hang-up."""
        while not self._stop.is_set():
            try:
                request = connection.recv(4096)
            except TimeoutError:
                continue
            except OSError:  # reset before sending: not ``hung_up``
                self.left_before_request = "reset"
                return None
            if not request:
                self.left_before_request = "eof"
                return None
            return request
        return None

    def _drip(self):
        connection = self._accept()
        if connection is None:
            return
        with connection:
            try:
                if self._receive_request(connection) is None:
                    return
                connection.settimeout(None)
                connection.sendall(self.prefix)
                for _ in range(60):
                    if self._stop.is_set():
                        return
                    connection.sendall(b"X")
                    time.sleep(0.05)
            except OSError:  # the client hung up or reset
                self.hung_up = True
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
