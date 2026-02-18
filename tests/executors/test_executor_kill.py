# mypy: no-strict-optional
"""Tests that check various kill behaviours."""

import errno
import os
import sys
import time
from typing import NoReturn, Set
from unittest.mock import patch

import pytest

from mirakuru import HTTPExecutor, SimpleExecutor
from mirakuru.compat import SIGKILL
from mirakuru.exceptions import ProcessFinishedWithError
from tests import SAMPLE_DAEMON_PATH, TEST_SERVER_PATH, list_processes
from tests.compat import SIGQUIT

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="POSIX-specific kill behavior not supported on Windows"
)

SLEEP_300 = "sleep 300"


def test_custom_signal_kill() -> None:
    """Start process and shuts it down using signal SIGQUIT."""
    executor = SimpleExecutor(SLEEP_300, kill_signal=SIGQUIT)
    executor.start()
    assert executor.running() is True
    executor.kill()
    assert executor.running() is False


def test_kill_custom_signal_kill() -> None:
    """Start process and shuts it down using signal SIGQUIT passed to kill."""
    executor = SimpleExecutor(SLEEP_300)
    executor.start()
    assert executor.running() is True
    executor.kill(sig=SIGQUIT)
    assert executor.running() is False


def test_already_closed() -> None:
    """Check that the executor cleans after itself after it exited earlier."""
    with pytest.raises(ProcessFinishedWithError) as excinfo:
        with SimpleExecutor("python") as executor:
            assert executor.running()
            os.killpg(executor.process.pid, SIGKILL)

            def process_stopped() -> bool:
                """Return True only only when self.process is not running."""
                return executor.running() is False

            executor.wait_for(process_stopped)
            assert executor.process
    assert excinfo.value.exit_code == -9
    assert not executor.process


@pytest.mark.xdist_group(name="sample-deamon")
def test_daemons_killing() -> None:
    """Test if all subprocesses of SimpleExecutor can be killed.

    The most problematic subprocesses are daemons or other services that
    change the process group ID. This test verifies that daemon process
    is killed after executor's kill().
    """
    executor = SimpleExecutor(("python", SAMPLE_DAEMON_PATH), shell=True)
    executor.start()
    time.sleep(2)
    assert executor.running() is not True, (
        "Executor should not have subprocess running as it started a daemon."
    )

    assert SAMPLE_DAEMON_PATH in list_processes()
    executor.kill()
    assert SAMPLE_DAEMON_PATH not in list_processes()


def test_stopping_brutally() -> None:
    """Test if SimpleExecutor is stopping insubordinate process.

    Check if the process that doesn't react to SIGTERM signal will be killed
    by executor with SIGKILL automatically.
    """
    host_port = "127.0.0.1:8000"
    cmd = f"{sys.executable} {TEST_SERVER_PATH} {host_port} True"
    executor = HTTPExecutor(cmd, f"http://{host_port!s}/", timeout=20)
    executor.start()
    assert executor.running() is True

    stop_at = time.time() + 10
    executor.stop()
    assert executor.running() is False
    assert stop_at <= time.time(), "Subprocess killed earlier than in 10 secs"


def test_stopping_children_of_stopped_process() -> None:
    """Check that children exiting between listing and killing are ignored.

    Given:
        Executor is running and it's process spawn children,
        and we requested it's stop, and it's stopped
    When:
        At the time of the check for subprocesses they're still active,
        but before we start killing them, they are already dead.
    Then:
        We ignore and skip OsError indicates there's no such process.
    """

    # pylint: disable=protected-access, missing-docstring
    def raise_os_error(*_: int, **__: int) -> NoReturn:
        os_error = OSError()
        os_error.errno = errno.ESRCH
        raise os_error

    def processes_with_env_mock(*_: str, **__: str) -> Set[int]:
        return {1}

    with (
        patch("mirakuru.base.processes_with_env", new=processes_with_env_mock),
        patch("os.kill", new=raise_os_error),
    ):
        executor = SimpleExecutor(SLEEP_300)
        executor._kill_all_kids(executor._stop_signal)
