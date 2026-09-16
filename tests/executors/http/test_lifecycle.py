"""HTTP executor start/stop tests."""

import socket
from unittest.mock import patch

import pytest

from mirakuru import AlreadyRunning, HTTPExecutor, TCPExecutor
from tests.executors.http.base import (
    HOST,
    HTTP_NORMAL_CMD,
    PORT,
    XDIST_GROUP,
    connect_to_server,
)

pytestmark = pytest.mark.xdist_group(name=XDIST_GROUP)


def test_executor_starts_and_waits() -> None:
    """Test if process awaits for HEAD request to be completed."""
    command = f'bash -c "sleep 3 && {HTTP_NORMAL_CMD}"'

    executor = HTTPExecutor(command, f"http://{HOST}:{PORT}/", timeout=20)
    executor.start()
    assert executor.running() is True

    connect_to_server()

    executor.stop()

    # check proper __str__ and __repr__ rendering:
    assert "HTTPExecutor" in repr(executor)
    assert command in str(executor)


def test_shell_started_server_stops() -> None:
    """Test if executor terminates properly executor with shell=True."""
    executor = HTTPExecutor(HTTP_NORMAL_CMD, f"http://{HOST}:{PORT}/", timeout=20, shell=True)

    with pytest.raises(socket.error):
        connect_to_server()

    with executor:
        assert executor.running() is True
        connect_to_server()

    assert executor.running() is False

    with pytest.raises(socket.error):
        connect_to_server()


def test_fail_if_other_running() -> None:
    """Test raising AlreadyRunning exception when port is blocked."""
    executor = HTTPExecutor(
        HTTP_NORMAL_CMD,
        f"http://{HOST}:{PORT}/",
    )
    executor2 = HTTPExecutor(
        HTTP_NORMAL_CMD,
        f"http://{HOST}:{PORT}/",
    )

    with executor:
        assert executor.running() is True

        with pytest.raises(AlreadyRunning):
            executor2.start()

        with pytest.raises(AlreadyRunning) as exc:
            with executor2:
                pass
        assert "seems to be already running" in str(exc.value)


@patch.object(HTTPExecutor, "DEFAULT_PORT", PORT)
def test_default_port() -> None:
    """Test default port for the base TCP check.

    Check if HTTP executor fills in the default port for the TCP check
    from the base class if no port is provided in the URL.
    """
    executor = HTTPExecutor(HTTP_NORMAL_CMD, f"http://{HOST}/")

    assert executor.url.port is None
    assert executor.port == PORT

    assert TCPExecutor.pre_start_check(executor) is False
    executor.start()
    assert TCPExecutor.pre_start_check(executor) is True
    executor.stop()
