# mypy: no-strict-optional
"""Test basic executor functionality."""

import gc
import math
import shlex
import signal
import sys
import uuid
from subprocess import check_output
from unittest import mock

import pytest

from mirakuru import Executor
from mirakuru.base import SimpleExecutor
from mirakuru.exceptions import ProcessExitedWithError, TimeoutExpired
from tests import (
    SAMPLE_DAEMON_PATH,
    SLEEP_300,
    SLEEP_300_LINE,
    WINDOWS,
    needs_posix_daemon,
    running_command_lines,
    signalled_exit_code,
)
from tests.retry import retry


@pytest.mark.parametrize("command", (SLEEP_300_LINE, SLEEP_300))
def test_running_process(command: str | list[str]) -> None:
    """Start process and shuts it down."""
    executor = SimpleExecutor(command)
    executor.start()
    assert executor.running() is True
    executor.stop()
    assert executor.running() is False

    # check proper __str__ and __repr__ rendering:
    assert "SimpleExecutor" in repr(executor)
    assert executor.command in str(executor)


@pytest.mark.parametrize(
    "command, expected_command",
    ((SLEEP_300_LINE, SLEEP_300_LINE), (SLEEP_300, shlex.join(SLEEP_300))),
)
def test_command(command: str | list[str], expected_command: str) -> None:
    """Check that the command and command parts are equivalent."""
    executor = SimpleExecutor(command)
    assert executor.command == expected_command
    assert list(executor.command_parts) == SLEEP_300


def test_custom_signal_stop() -> None:
    """Start process and shuts it down using signal SIGABRT."""
    executor = SimpleExecutor(SLEEP_300, stop_signal=signal.SIGABRT)
    executor.start()
    assert executor.running() is True
    executor.stop()
    assert executor.running() is False


def test_stop_custom_signal_stop() -> None:
    """Start process and shuts it down using signal SIGABRT passed to stop."""
    executor = SimpleExecutor(SLEEP_300)
    executor.start()
    assert executor.running() is True
    executor.stop(stop_signal=signal.SIGABRT)
    assert executor.running() is False


def test_stop_custom_exit_signal_stop() -> None:
    """Start process and expect it to finish with custom signal."""
    executor = SimpleExecutor(f'"{sys.executable}" -c "raise SystemExit(1)"', shell=True)
    executor.start()
    # the command exits instantly, so there should not be a process to stop
    expected_returncode = signalled_exit_code(signal.SIGABRT)
    retry(
        lambda: executor.stop(stop_signal=signal.SIGABRT, expected_returncode=expected_returncode)
    )
    assert executor.running() is False


def test_stop_custom_exit_signal_context() -> None:
    """Start a process and expect a custom exit signal in the context manager."""
    with SimpleExecutor(
        SLEEP_300, expected_returncode=signalled_exit_code(signal.SIGABRT)
    ) as executor:
        executor.stop(stop_signal=signal.SIGABRT)
        assert executor.running() is False


def test_running_context() -> None:
    """Start process and shuts it down."""
    executor = SimpleExecutor(SLEEP_300)
    with executor:
        assert executor.running() is True

    assert executor.running() is False


def test_executor_in_context_only() -> None:
    """Start a process and shuts it down only in context."""
    with SimpleExecutor(SLEEP_300) as executor:
        assert executor.running() is True


def test_context_stopped() -> None:
    """Start for context and shuts it for nested context."""
    executor = SimpleExecutor(SLEEP_300)
    with executor:
        assert executor.running() is True
        with executor.stopped():
            assert executor.running() is False
        assert executor.running() is True

    assert executor.running() is False


ECHO_FOOBAR = [sys.executable, "-c", "print('foobar')"]
ECHO_FOOBAR_LINE = f'"{sys.executable}" -c "print(\'foobar\')"'


@pytest.mark.parametrize("command", (ECHO_FOOBAR_LINE, ECHO_FOOBAR))
def test_process_output(command: str | list[str]) -> None:
    """Start a process, check output and shut it down."""
    executor = SimpleExecutor(command)
    executor.start()

    assert executor.output().read() == "foobar\n"
    executor.stop()


@pytest.mark.parametrize(
    "command",
    (
        ECHO_FOOBAR_LINE,
        pytest.param(
            ECHO_FOOBAR,
            marks=pytest.mark.skipif(
                WINDOWS,
                reason="The command is joined with POSIX quoting, which cmd.exe does not read.",
            ),
        ),
    ),
)
def test_process_output_shell(command: str | list[str]) -> None:
    """Start process, check output and shut it down with shell set to True."""
    executor = SimpleExecutor(command, shell=True)
    executor.start()

    assert executor.output().read().strip() == "foobar"
    executor.stop()


def test_start_check_executor() -> None:
    """Validate Executor base class having NotImplemented methods."""
    executor = Executor(SLEEP_300)
    with pytest.raises(NotImplementedError):
        executor.pre_start_check()
    with pytest.raises(NotImplementedError):
        executor.after_start_check()


def test_stopping_not_yet_running_executor() -> None:
    """Test if SimpleExecutor can be stopped even it was never running.

    We must make sure that it's possible to call .stop() and SimpleExecutor
    will not raise any exception and .start() can be called afterwards.
    """
    executor = SimpleExecutor(SLEEP_300)
    executor.stop()
    executor.start()
    assert executor.running() is True
    executor.stop()


def test_forgotten_stop() -> None:
    """Test if SimpleExecutor subprocess is killed after an instance is deleted.

    Existence can end because of context scope end or by calling 'del'.
    If someone forgot to stop() or kill() subprocess it should be killed
    by default on instance cleanup.
    """
    mark = uuid.uuid1().hex
    marked_command = [sys.executable, "-c", f"import time; time.sleep(300)  # {mark}"]
    executor = SimpleExecutor(marked_command)
    executor.start()
    assert executor.running() is True
    command_lines = running_command_lines()
    assert mark in command_lines, (
        f"The test command {marked_command} should be running in \n\n {command_lines}."
    )
    del executor
    gc.collect()  # to force 'del' immediate effect
    assert mark not in running_command_lines(), (
        "The test process should not be running at this point."
    )


def test_executor_raises_if_process_exits_with_error() -> None:
    """Test process exit detection.

    If the process exits with an error while checks are being polled, executor
    should raise an exception.
    """
    error_code = 12
    failing_executor = Executor(
        [sys.executable, "-c", f"raise SystemExit({error_code!s})"], timeout=5
    )
    failing_executor.pre_start_check = mock.Mock(return_value=False)  # type: ignore
    # After-start check will keep returning False to let the process terminate.
    failing_executor.after_start_check = mock.Mock(return_value=False)  # type: ignore

    with pytest.raises(ProcessExitedWithError) as exc:
        failing_executor.start()

    assert exc.value.exit_code == 12
    error_msg = f"exited with a non-zero code: {error_code!s}"
    assert error_msg in str(exc.value)

    # Pre-start check should have been called - after-start check might or
    # might not have been called - depending on the timing.
    assert failing_executor.pre_start_check.called is True


def test_executor_ignores_processes_exiting_with_0() -> None:
    """Test process exit detection.

    Subprocess exiting with zero should be tolerated in order to support
    double-forking applications.
    """
    # We execute a process that will return zero. In order to give the process
    # enough time to return we keep the polling loop spinning for a second.
    executor = Executor([sys.executable, "-c", "raise SystemExit(0)"], timeout=1.0)
    executor.pre_start_check = mock.Mock(return_value=False)  # type: ignore
    executor.after_start_check = mock.Mock(return_value=False)  # type: ignore

    with pytest.raises(TimeoutExpired):
        # We keep the post-checks spinning forever so it eventually times out.
        executor.start()

    # Both checks should have been called.
    assert executor.pre_start_check.called is True
    assert executor.after_start_check.called is True


def test_executor_methods_returning_self() -> None:
    """Test if SimpleExecutor lets to chain start, stop and kill methods."""
    executor = SimpleExecutor(SLEEP_300).start().stop().kill().stop()
    assert not executor.running()

    # Check if context manager returns executor to use it in 'as' phrase:
    with SimpleExecutor(SLEEP_300) as executor:
        assert executor.running()

    with SimpleExecutor(SLEEP_300).start().stopped() as executor:
        assert not executor.running()

    assert SimpleExecutor(SLEEP_300).start().stop().output


@needs_posix_daemon
@pytest.mark.xdist_group(name="sample-deamon")
def test_mirakuru_cleanup() -> None:
    """Test if cleanup_subprocesses is fired correctly on python exit."""
    cmd = f"""
        python -c 'from mirakuru import SimpleExecutor;
                   from time import sleep;
                   import gc;
                   gc.disable();
                   ex = SimpleExecutor(
                       ("python", "{SAMPLE_DAEMON_PATH}")).start();
                   sleep(1);
                  '
    """
    check_output(shlex.split(cmd.replace("\n", "")))
    assert SAMPLE_DAEMON_PATH not in running_command_lines()


def test_remaining_timeout() -> None:
    """Check that the remaining timeout shrinks along with the wait."""
    executor = SimpleExecutor(SLEEP_300, timeout=5)

    executor.start()
    try:
        assert executor._remaining_timeout == pytest.approx(5, abs=0.5)

        with mock.patch("mirakuru.base.time.time", return_value=executor._endtime - 2):
            assert executor._remaining_timeout == 2
    finally:
        executor.stop()


def test_remaining_timeout_does_not_go_negative() -> None:
    """Check that the remaining timeout is clamped once the deadline has passed."""
    executor = SimpleExecutor(SLEEP_300, timeout=5)

    executor.start()
    try:
        with mock.patch("mirakuru.base.time.time", return_value=executor._endtime + 10):
            assert executor._remaining_timeout == 0
            assert executor.check_timeout() is False
    finally:
        executor.stop()


def test_remaining_timeout_without_deadline() -> None:
    """Check that an executor with no deadline set has no timeout to run down.

    ``check_timeout`` reads a ``None`` ``_endtime`` as "wait indefinitely", so
    the remaining timeout has to agree with it rather than report 0 seconds
    left.
    """
    executor = SimpleExecutor(SLEEP_300, timeout=5)

    assert executor._endtime is None
    assert executor._remaining_timeout == math.inf
    assert executor.check_timeout() is True


def test_check_timeout_implies_time_left() -> None:
    """Check that a live timeout always leaves a non-zero amount of it.

    Callers derive a budget from ``_remaining_timeout`` while ``check_timeout``
    holds - `HTTPExecutor.after_start_check` arms its connection with it - and
    a 0 there means "don't block at all" rather than "no time left".
    """
    executor = SimpleExecutor(SLEEP_300, timeout=5)

    executor.start()
    try:
        for offset in (0, 1, 4.999, 5, 6):
            with mock.patch("mirakuru.base.time.time", return_value=executor._endtime - offset):
                if executor.check_timeout():
                    assert executor._remaining_timeout > 0
    finally:
        executor.stop()
