"""HTTP Executor tests."""

import math
import socket
import sys
import threading
import time
from functools import partial
from http.client import OK, HTTPConnection
from typing import Any
from unittest.mock import PropertyMock, patch

import pytest

from mirakuru import AlreadyRunning, HTTPExecutor, TCPExecutor, TimeoutExpired
from tests import HTTP_SERVER_CMD, TEST_SERVER_PATH

HOST = "127.0.0.1"
PORT = 7987

HTTP_NORMAL_CMD = f"{HTTP_SERVER_CMD} {PORT}"
HTTP_SLOW_CMD = f"{sys.executable} {TEST_SERVER_PATH} {HOST}:{PORT}"
HTTP_HANGING_CMD = f"{sys.executable} {TEST_SERVER_PATH} {HOST}:{PORT} False Hang"

HANG_DEADLINE = 30
"""Wall clock bound for the hanging-server tests, well above their own timeouts."""

pytestmark = pytest.mark.xdist_group(name=f"http-port-{PORT}")


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


def start_bounded(executor: HTTPExecutor, deadline: float) -> None:
    """Run ``executor.start()`` on a daemon thread and fail if it outlives deadline.

    #1175 is a hang, so an unbounded ``start()`` would take the whole test run
    down with it rather than report a failure. The thread is a daemon so that
    pytest can still exit while a regressed ``start()`` is stuck in the socket.
    """
    error: list[BaseException] = []

    def run() -> None:
        try:
            executor.start()
        except BaseException as err:  # pylint:disable=broad-except
            error.append(err)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(deadline)
    assert not thread.is_alive(), f"executor.start() still blocked after {deadline}s"
    if error:
        raise error[0]


def test_hanging_server_times_out() -> None:
    """Check that a server which never answers does not wedge the executor.

    Regression test for #1175: the check connection used to be opened without
    any timeout, so ``getresponse()`` blocked forever and ``wait_for`` never
    regained control to notice its own deadline had passed.
    """
    executor = HTTPExecutor(HTTP_HANGING_CMD, f"http://{HOST}:{PORT}/", timeout=2)

    start = time.time()
    try:
        with pytest.raises(TimeoutExpired):
            start_bounded(executor, deadline=HANG_DEADLINE)
    finally:
        executor.kill()
    elapsed = time.time() - start

    assert executor.running() is False
    # The executor spends its whole budget retrying, but not a lot more.
    assert 2 <= elapsed < HANG_DEADLINE


def test_hanging_server_request_timeout() -> None:
    """Check that `request_timeout` bounds a single check, not the whole wait.

    With a per-request timeout well below the executor's own budget the check
    gets retried a few times and only then the executor gives up.
    """
    executor = HTTPExecutor(
        HTTP_HANGING_CMD, f"http://{HOST}:{PORT}/", timeout=4, request_timeout=1
    )

    start = time.time()
    try:
        with pytest.raises(TimeoutExpired):
            start_bounded(executor, deadline=HANG_DEADLINE)
    finally:
        executor.kill()
    elapsed = time.time() - start

    assert executor.running() is False
    assert 4 <= elapsed < HANG_DEADLINE


@pytest.mark.parametrize(
    ("request_timeout", "timeout", "remaining", "expected"),
    (
        # no request_timeout: the executor's own budget bounds the connection
        (None, 10, 10.0, 10),
        # ... and so does whatever is left of it
        (None, 10, 2.5, 2.5),
        # an explicit request_timeout wins while it is the shorter one
        (1, 10, 10.0, 1),
        # ... but never lets a single check outlive the remaining budget
        (30, 10, 4.0, 4.0),
        # no deadline set yet: only the executor's timeout applies
        (None, 10, math.inf, 10),
        (2, 10, math.inf, 2),
        # 0 reads as unset, same as None
        (0, 10, math.inf, 10),
        # fractional timeouts pass through untouched
        (0.5, 10, math.inf, 0.5),
    ),
)
def test_check_connection_timeout(
    request_timeout: int | None,
    timeout: int,
    remaining: float,
    expected: float,
) -> None:
    """Check the timeout `after_start_check` arms the check connection with."""
    executor = HTTPExecutor(
        HTTP_NORMAL_CMD,
        f"http://{HOST}:{PORT}/",
        timeout=timeout,
        request_timeout=request_timeout,
    )

    with (
        patch.object(
            HTTPExecutor, "_remaining_timeout", new_callable=PropertyMock
        ) as remaining_mock,
        patch("mirakuru.http.HTTPConnection") as connection_mock,
    ):
        remaining_mock.return_value = remaining
        connection_mock.return_value.getresponse.return_value.status = 200

        assert executor.after_start_check() is True

    assert connection_mock.call_args.kwargs["timeout"] == expected


def test_check_connection_timeout_expires() -> None:
    """Check that a check connection timing out is reported as 'not started yet'."""
    executor = HTTPExecutor(HTTP_NORMAL_CMD, f"http://{HOST}:{PORT}/", timeout=10)

    with patch("mirakuru.http.HTTPConnection") as connection_mock:
        connection_mock.return_value.getresponse.side_effect = socket.timeout

        assert executor.after_start_check() is False


def test_check_connection_timeout_without_deadline() -> None:
    """Check that a check run outside a start/stop wait still blocks normally.

    ``after_start_check`` is public, and until ``start()`` sets a deadline the
    remaining timeout is infinite - so the connection has to fall back to the
    executor's own timeout. A 0 here would put the socket in non-blocking mode
    and make every check fail with ``BlockingIOError``.
    """
    executor = HTTPExecutor(HTTP_NORMAL_CMD, f"http://{HOST}:{PORT}/", timeout=10)

    assert executor._endtime is None

    with patch("mirakuru.http.HTTPConnection") as connection_mock:
        connection_mock.return_value.getresponse.return_value.status = 200

        assert executor.after_start_check() is True

    assert connection_mock.call_args.kwargs["timeout"] == 10


def test_negative_request_timeout() -> None:
    """Check that a negative request timeout is rejected on construction.

    ``socket.settimeout`` would otherwise raise ``ValueError`` on the first
    check instead - well past the point where the mistake is easy to place,
    and out of reach of `after_start_check`'s own ``except`` clause, which
    only covers ``OSError`` and ``HTTPException``.
    """
    with pytest.raises(ValueError, match="request_timeout must not be negative"):
        HTTPExecutor(HTTP_NORMAL_CMD, f"http://{HOST}:{PORT}/", request_timeout=-1)


def test_url_without_hostname() -> None:
    """Check that a url with no hostname is rejected on construction.

    Also covers the half-built executor this leaves behind: ``__init__`` raises
    before `SimpleExecutor.__init__` has set ``process``, so ``__del__`` has to
    cope with the attribute being absent.
    """
    with pytest.raises(ValueError, match="does not contain hostname"):
        HTTPExecutor(HTTP_NORMAL_CMD, "http:///nohost")
