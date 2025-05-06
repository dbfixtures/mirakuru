"""TCPExecutor tests.

Some of these tests run ``nc``: when running Debian, make sure the
``netcat-openbsd`` package is used, not ``netcat-traditional``.
"""

import logging
import socket
from typing import Any

import pytest
from _pytest.logging import LogCaptureFixture

from mirakuru import AlreadyRunning, TCPExecutor, TimeoutExpired
from tests import HTTP_SERVER_CMD


# Allocate a random free port to avoid hardcoding and risking hitting an
# occupied one; then let its number be reused elsewhere (by `nc`).
def _find_free_port() -> Any:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


test_port = _find_free_port()


PORT = 7986
HTTP_SERVER = f"{HTTP_SERVER_CMD} {PORT}"
NC_COMMAND = f'bash -c "sleep 2 && nc -lk {test_port}"'


def test_start_and_wait(caplog: LogCaptureFixture) -> None:
    """Test if executor await for process to accept connections."""
    caplog.set_level(logging.DEBUG, logger="mirakuru")
    executor = TCPExecutor(NC_COMMAND, "localhost", port=test_port, timeout=5)
    executor.start()
    assert executor.running() is True
    executor.stop()


def test_repr_and_str() -> None:
    """Check the proper str and repr conversion."""
    executor = TCPExecutor(NC_COMMAND, "localhost", port=test_port, timeout=5)
    # check proper __str__ and __repr__ rendering:
    assert "TCPExecutor" in repr(executor)
    assert NC_COMMAND in str(executor)


def test_it_raises_error_on_timeout() -> None:
    """Check if TimeoutExpired gets raised correctly."""
    command = f'bash -c "sleep 10 && nc -lk {test_port}"'
    executor = TCPExecutor(command, host="localhost", port=test_port, timeout=2)

    with pytest.raises(TimeoutExpired):
        executor.start()

    assert executor.running() is False


def test_fail_if_other_executor_running() -> None:
    """Test raising AlreadyRunning exception."""
    executor = TCPExecutor(HTTP_SERVER, host="localhost", port=PORT)
    executor2 = TCPExecutor(HTTP_SERVER, host="localhost", port=PORT)

    with executor:
        assert executor.running() is True

        with pytest.raises(AlreadyRunning):
            executor2.start()

        with pytest.raises(AlreadyRunning):
            with executor2:
                pass
