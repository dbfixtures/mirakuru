"""HTTP executor tests against a server that is slow to become ready."""

import sys

import pytest

from mirakuru import HTTPExecutor, TimeoutExpired
from tests import TEST_SERVER_PATH
from tests.executors.http.base import HOST, PORT, XDIST_GROUP, connect_to_server

pytestmark = pytest.mark.xdist_group(name=XDIST_GROUP)


@pytest.mark.parametrize("method", ("HEAD", "GET", "POST"))
def test_slow_method_server_starting(method: str) -> None:
    """Test whether or not executor awaits for slow starting servers.

    Simple example. You run Gunicorn and it is working but you have to
    wait for worker processes.
    """
    http_method_slow_cmd = f"{sys.executable} {TEST_SERVER_PATH} {HOST}:{PORT} False {method}"
    with HTTPExecutor(
        http_method_slow_cmd,
        f"http://{HOST}:{PORT}/",
        method=method,
        timeout=30,
    ) as executor:
        assert executor.running() is True
        connect_to_server()


def test_slow_post_payload_server_starting() -> None:
    """Test whether or not executor awaits for slow starting servers.

    Simple example. You run Gunicorn and it is working but you have to
    wait for worker processes.
    """
    http_method_slow_cmd = f"{sys.executable} {TEST_SERVER_PATH} {HOST}:{PORT} False Key"
    with HTTPExecutor(
        http_method_slow_cmd,
        f"http://{HOST}:{PORT}/",
        method="POST",
        timeout=30,
        payload={"key": "hole"},
    ) as executor:
        assert executor.running() is True
        connect_to_server()


@pytest.mark.parametrize("method", ("HEAD", "GET", "POST"))
def test_slow_method_server_timed_out(method: str) -> None:
    """Check if timeout properly expires."""
    http_method_slow_cmd = f"{sys.executable} {TEST_SERVER_PATH} {HOST}:{PORT} False {method}"
    executor = HTTPExecutor(
        http_method_slow_cmd, f"http://{HOST}:{PORT}/", method=method, timeout=1
    )

    with pytest.raises(TimeoutExpired) as exc:
        executor.start()

    assert executor.running() is False
    assert "timed out after" in str(exc.value)
