"""HTTP Executor tests."""

import socket
import sys
from functools import partial
from http.client import OK, HTTPConnection
from typing import Any
from unittest.mock import patch

import pytest

from mirakuru import AlreadyRunning, HTTPExecutor, TCPExecutor, TimeoutExpired
from tests import HTTP_SERVER_CMD, TEST_SERVER_PATH

HOST = "127.0.0.1"
PORT = 7987

HTTP_NORMAL_CMD = f"{HTTP_SERVER_CMD} {PORT}"
HTTP_SLOW_CMD = f"{sys.executable} {TEST_SERVER_PATH} {HOST}:{PORT}"


slow_server_executor = partial(  # pylint: disable=invalid-name
    HTTPExecutor,
    HTTP_SLOW_CMD,
    f"http://{HOST}:{PORT}/",
)


def connect_to_server() -> None:
    """Connect to http server and assert 200 response."""
    conn = HTTPConnection(HOST, PORT)
    conn.request("GET", "/")
    assert conn.getresponse().status == OK
    conn.close()


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


@pytest.mark.parametrize(
    "accepted_status, expected_timeout",
    (
        # default behaviour - only 2XX HTTP status codes are accepted
        (None, True),
        # one explicit integer status code
        (200, True),
        # one explicit status code as a string
        ("404", False),
        # status codes as a regular expression
        (r"(2|4)\d\d", False),
        # status codes as a regular expression
        ("(200|404)", False),
    ),
)
def test_http_status_codes(accepted_status: None | int | str, expected_timeout: bool) -> None:
    """Test how 'status' argument influences executor start.

    :param int|str accepted_status: Executor 'status' value
    :param bool expected_timeout: if Executor raises TimeoutExpired or not
    """
    kwargs: dict[str, Any] = {
        "command": HTTP_NORMAL_CMD,
        "url": f"http://{HOST}:{PORT}/badpath",
        "timeout": 2,
    }
    if accepted_status:
        kwargs["status"] = accepted_status
    executor = HTTPExecutor(**kwargs)

    if not expected_timeout:
        executor.start()
        executor.stop()
    else:
        with pytest.raises(TimeoutExpired):
            executor.start()
            executor.stop()
