"""TCPExecutor tests.

Some of these tests run ``nc``: when running Debian, make sure the
``netcat-openbsd`` package is used, not ``netcat-traditional``.
"""

import sys

import pytest

from mirakuru import TimeoutExpired
from mirakuru.unixsocket import UnixSocketExecutor
from tests import TEST_SOCKET_SERVER_PATH

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="Unix socket tests are not supported on Windows"
)


def test_start_and_wait(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Test if executor await for process to accept connections."""
    socker_path = tmp_path_factory.getbasetemp() / "mirakuru.sock"
    socket_server_cmd = f"{sys.executable} {TEST_SOCKET_SERVER_PATH} {socker_path}"
    executor = UnixSocketExecutor(socket_server_cmd + " 2", socket_name=str(socker_path), timeout=5)
    with executor:
        assert executor.running() is True


def test_start_and_timeout(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Test if executor will properly time out."""
    socker_path = tmp_path_factory.getbasetemp() / "mirakuru.sock"
    socket_server_cmd = f"{sys.executable} {TEST_SOCKET_SERVER_PATH} {socker_path}"
    executor = UnixSocketExecutor(
        socket_server_cmd + " 10", socket_name=str(socker_path), timeout=5
    )

    with pytest.raises(TimeoutExpired):
        executor.start()

    assert executor.running() is False
