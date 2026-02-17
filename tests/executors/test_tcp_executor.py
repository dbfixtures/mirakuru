"""TCPExecutor tests."""

import logging
import socket
import sys

import pytest
from _pytest.logging import LogCaptureFixture

from mirakuru import AlreadyRunning, TCPExecutor, TimeoutExpired
from tests import HTTP_SERVER_CMD


# Allocate a random free port to avoid hardcoding and risking hitting an
# occupied one; then let its number be reused elsewhere (by the listener).
def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return int(s.getsockname()[1])


def nc_command(port: int, sleep_seconds: int = 2) -> str:
    """Construct a command to start a TCP listener on the specified port."""
    # Use Python's socket module instead of nc to avoid depending on netcat.
    # chr(0)*0 evaluates to '' (empty string) to bind on all interfaces
    # without embedding quote characters that would break shell quoting.
    return (
        f"{sys.executable} -c "
        f"'import time,socket; time.sleep({sleep_seconds}); "
        f"s=socket.socket(); "
        f"s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); "
        f"s.bind((chr(0)*0,{port})); "
        f"s.listen(1); "
        f"time.sleep(300)'"
    )


def test_start_and_wait(caplog: LogCaptureFixture) -> None:
    """Test if the executor awaits for a process to accept connections."""
    test_port = _find_free_port()
    caplog.set_level(logging.DEBUG, logger="mirakuru")
    executor = TCPExecutor(nc_command(test_port), "localhost", port=test_port, timeout=5)
    executor.start()
    assert executor.running() is True
    executor.stop()


def test_repr_and_str() -> None:
    """Check the proper str and repr conversion."""
    test_port = _find_free_port()
    nc = nc_command(test_port)
    executor = TCPExecutor(nc, "localhost", port=test_port, timeout=5)
    # check proper __str__ and __repr__ rendering:
    assert "TCPExecutor" in repr(executor)
    assert nc in str(executor)


def test_it_raises_error_on_timeout() -> None:
    """Check if TimeoutExpired gets raised correctly."""
    test_port = _find_free_port()
    executor = TCPExecutor(nc_command(test_port, 10), host="localhost", port=test_port, timeout=2)

    with pytest.raises(TimeoutExpired):
        executor.start()

    assert executor.running() is False


def test_fail_if_other_executor_running() -> None:
    """Test raising AlreadyRunning exception."""
    test_port = _find_free_port()
    http_server = f"{HTTP_SERVER_CMD} {test_port}"
    executor = TCPExecutor(http_server, host="localhost", port=test_port)
    executor2 = TCPExecutor(http_server, host="localhost", port=test_port)

    with executor:
        assert executor.running() is True

        with pytest.raises(AlreadyRunning):
            executor2.start()

        with pytest.raises(AlreadyRunning):
            with executor2:
                pass
