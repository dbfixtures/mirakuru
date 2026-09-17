"""HTTP executor tests for the timeout bounding the status check itself."""

import math
import socket
import sys
import threading
import time
from unittest.mock import PropertyMock, patch

import pytest

from mirakuru import HTTPExecutor, TimeoutExpired
from tests import TEST_SERVER_PATH
from tests.executors.http.base import HOST, HTTP_NORMAL_CMD, PORT, XDIST_GROUP

pytestmark = pytest.mark.xdist_group(name=XDIST_GROUP)

HTTP_HANGING_CMD = f"{sys.executable} {TEST_SERVER_PATH} {HOST}:{PORT} False Hang"

HANG_DEADLINE = 30
"""Wall clock bound for the hanging-server tests, well above their own timeouts."""


def start_bounded(executor: HTTPExecutor, deadline: float) -> None:
    """Run ``executor.start()`` on a daemon thread and fail if it outlives the deadline."""
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
    """Check that a server which never answers does not wedge the executor."""
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
    """Check that `request_timeout` bounds a single check, not the whole wait."""
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
    """Check that a check run outside a start/stop wait still blocks normally."""
    executor = HTTPExecutor(HTTP_NORMAL_CMD, f"http://{HOST}:{PORT}/", timeout=10)

    assert executor._endtime is None

    with patch("mirakuru.http.HTTPConnection") as connection_mock:
        connection_mock.return_value.getresponse.return_value.status = 200

        assert executor.after_start_check() is True

    assert connection_mock.call_args.kwargs["timeout"] == 10
