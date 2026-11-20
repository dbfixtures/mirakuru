# mypy: no-strict-optional
"""Tests that check various kill behaviours."""

import errno
import os
import signal
import sys
import time
import uuid
from pathlib import Path
from typing import NoReturn
from unittest.mock import MagicMock, patch

import psutil
import pytest

from mirakuru import HTTPExecutor, SimpleExecutor
from mirakuru.base import ENV_UUID, STATUS_CONTROL_C_EXIT, signal_process_tree
from mirakuru.exceptions import ProcessFinishedWithError
from tests import (
    SAMPLE_DAEMON_PATH,
    SLEEP_300,
    TEST_SERVER_PATH,
    needs_posix_daemon,
    running_command_lines,
    signalled_exit_code,
    skip_on_windows,
)


def test_custom_signal_kill() -> None:
    """Start process and shuts it down using signal SIGABRT."""
    executor = SimpleExecutor(SLEEP_300, kill_signal=signal.SIGABRT)
    executor.start()
    assert executor.running() is True
    executor.kill()
    assert executor.running() is False


def test_kill_custom_signal_kill() -> None:
    """Start process and shuts it down using signal SIGABRT passed to kill."""
    executor = SimpleExecutor(SLEEP_300)
    executor.start()
    assert executor.running() is True
    executor.kill(sig=signal.SIGABRT)
    assert executor.running() is False


def test_already_closed() -> None:
    """Check that the executor cleans after itself after it exited earlier."""
    with pytest.raises(ProcessFinishedWithError) as excinfo:
        with SimpleExecutor([sys.executable]) as executor:
            assert executor.running()
            os.kill(executor.process.pid, signal.SIGABRT)

            def process_stopped() -> bool:
                """Return True only only when self.process is not running."""
                return executor.running() is False

            executor.wait_for(process_stopped)
            assert executor.process
    assert excinfo.value.exit_code == signalled_exit_code(signal.SIGABRT)
    assert not executor.process


@needs_posix_daemon
@pytest.mark.xdist_group(name="sample-deamon")
def test_daemons_killing() -> None:
    """Test if all subprocesses of SimpleExecutor can be killed.

    The most problematic subprocesses are daemons or other services that
    change the process group ID. This test verifies that daemon process
    is killed after executor's kill().
    """
    executor = SimpleExecutor((sys.executable, SAMPLE_DAEMON_PATH))
    executor.start()
    time.sleep(2)
    assert executor.running() is not True, (
        "Executor should not have subprocess running as it started a daemon."
    )

    assert SAMPLE_DAEMON_PATH in running_command_lines()
    executor.kill()
    assert SAMPLE_DAEMON_PATH not in running_command_lines()


@skip_on_windows(issue=1216)
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

    def processes_with_env_mock(*_: str, **__: str) -> set[int]:
        return {1}

    with (
        patch("mirakuru.base.processes_with_env", new=processes_with_env_mock),
        patch("os.kill", new=raise_os_error),
    ):
        executor = SimpleExecutor(SLEEP_300)
        executor._kill_all_kids(executor._stop_signal)


@pytest.mark.skipif(sys.platform == "win32", reason="Windows has no process groups to signal.")
def test_stop__signals_process_group_member_outside_tree() -> None:
    """Check that stop reaches a process group member whose parent has exited.

    Such a worker is reparented away from the executor's process, so it is
    not a descendant anymore, and without the environment marker the leftover
    search cannot find it either.
    """
    # Given
    mark = uuid.uuid4().hex
    worker_code = f"import time; time.sleep(300)  # {mark}"
    intermediary_code = (
        f"import subprocess, sys; subprocess.Popen([sys.executable, '-c', {worker_code!r}])"
    )
    root_code = (
        "import os, subprocess, sys, time; "
        f"env = {{k: v for k, v in os.environ.items() if k != {ENV_UUID!r}}}; "
        f"subprocess.Popen([sys.executable, '-c', {intermediary_code!r}], env=env); "
        "time.sleep(300)"
    )
    executor = SimpleExecutor([sys.executable, "-c", root_code]).start()
    deadline = time.time() + 10
    while mark not in running_command_lines():
        assert time.time() < deadline, "The worker process did not start."
        time.sleep(0.1)

    # When
    executor.stop()

    # Then
    deadline = time.time() + 10
    while mark in running_command_lines():
        assert time.time() < deadline, "The worker process outlived the executor."
        time.sleep(0.1)


windows_only = pytest.mark.skipif(
    sys.platform != "win32", reason="Console control events exist on Windows only."
)


@windows_only
@pytest.mark.skipif(
    sys.implementation.name == "pypy",
    reason="PyPy doesn't exit on a console control event it has no handler for.",
)
def test_stop__ctrl_break_event(tmp_path: Path) -> None:
    """Check that a process ended by a console control event stops without an error."""
    # Given
    ready_path = tmp_path / "ready"
    executor = SimpleExecutor(
        [
            sys.executable,
            "-c",
            f"import pathlib, time; pathlib.Path({str(ready_path)!r}).touch(); time.sleep(300)",
        ],
        timeout=10,
        stop_signal=signal.CTRL_BREAK_EVENT,  # type: ignore[attr-defined,unused-ignore]
    ).start()
    # An event that arrives while the process is still loading ends it with
    # STATUS_DLL_INIT_FAILED instead.
    deadline = time.time() + 10
    while not ready_path.exists():
        assert time.time() < deadline, "The process did not start."
        time.sleep(0.1)
    process = executor.process

    # When
    executor.stop()

    # Then
    assert executor.running() is False
    assert process.returncode == STATUS_CONTROL_C_EXIT


@windows_only
def test_stop__ctrl_break_event_lets_process_tree_shut_down(tmp_path: Path) -> None:
    """Check that the process and its descendants handle the event and exit on their own."""
    # Given
    ready_path = tmp_path / "ready"
    stopped_path = tmp_path / "stopped"
    child_code = (
        "import pathlib, signal, sys, time\n"
        "def stop(*_):\n"
        f"    pathlib.Path({str(stopped_path)!r}).touch()\n"
        "    sys.exit(0)\n"
        "signal.signal(signal.SIGBREAK, stop)\n"
        f"pathlib.Path({str(ready_path)!r}).touch()\n"
        "while True:\n"
        "    time.sleep(0.1)\n"
    )
    root_code = (
        "import signal, subprocess, sys, time\n"
        "def stop(*_):\n"
        "    child.wait()\n"
        "    sys.exit(0)\n"
        "signal.signal(signal.SIGBREAK, stop)\n"
        f"child = subprocess.Popen([sys.executable, '-c', {child_code!r}])\n"
        "while True:\n"
        "    time.sleep(0.1)\n"
    )
    executor = SimpleExecutor(
        [sys.executable, "-c", root_code],
        stop_signal=signal.CTRL_BREAK_EVENT,  # type: ignore[attr-defined,unused-ignore]
    ).start()
    deadline = time.time() + 10
    while not ready_path.exists():
        assert time.time() < deadline, "The child process did not start."
        time.sleep(0.1)

    # When
    executor.stop()

    # Then
    assert stopped_path.exists()


def test_signal_process_tree__skips_exited_descendant() -> None:
    """Check that a descendant which exited after listing is not signalled.

    Its process ID may already belong to an unrelated process.
    """
    # Given
    descendant_mock = MagicMock(spec=psutil.Process, pid=999999)
    descendant_mock.is_running.return_value = False
    root_mock = MagicMock(spec=psutil.Process)
    root_mock.children.return_value = [descendant_mock]

    with (
        patch("mirakuru.base.psutil.Process", return_value=root_mock),
        patch("mirakuru.base.os.kill") as kill_mock,
    ):
        # When
        signal_process_tree(12345, signal.SIGTERM)

    # Then
    signalled_pids = [call.args[0] for call in kill_mock.call_args_list]
    assert descendant_mock.pid not in signalled_pids
