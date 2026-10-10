"""Shared fixtures for the forum host's tests."""

import socket
import threading
import time

import pytest


@pytest.fixture
def loopback_drip():
    """Start a loopback server that answers with ``prefix``, then drips a
    byte every 50 ms for 3 s: ``loopback_drip(prefix) -> port``. Every
    server is closed and its thread joined when the test ends (todo 539
    item 7; this was a helper the page tests imported from the image
    tests' module)."""
    started = []

    def start(prefix):
        server = socket.create_server(("127.0.0.1", 0))

        def drip():
            try:
                connection, _ = server.accept()
            except OSError:  # closed before anything connected
                return
            with connection:
                connection.recv(4096)
                connection.sendall(prefix)
                for _ in range(60):
                    try:
                        connection.sendall(b"X")
                    except OSError:
                        return
                    time.sleep(0.05)

        thread = threading.Thread(target=drip, daemon=True)
        thread.start()
        started.append((server, thread))
        return server.getsockname()[1]

    yield start
    for server, thread in started:
        server.close()
        thread.join(5)
