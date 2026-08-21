# mypy: no-strict-optional
"""Output executor test."""

import subprocess
import time

import pytest

from mirakuru import OutputExecutor
from mirakuru.exceptions import TimeoutExpired


def test_executor_waits_for_process_output() -> None:
    """Check if executor waits for specified output."""
    command = 'bash -c "sleep 2 && echo foo && echo bar && sleep 100"'
    executor = OutputExecutor(command, "foo", timeout=10).start()

    assert executor.running() is True
    # foo has been used for start as a banner.
    assert executor.output().readline() == "bar\n"
    executor.stop()

    # check proper __str__ and __repr__ rendering:
    assert "OutputExecutor" in repr(executor)
    assert "foo" in str(executor)


def test_executor_waits_for_process_err_output() -> None:
    """Check if executor waits for specified error output."""
    command = 'bash -c "sleep 2 && >&2 echo foo && >&2 echo bar && sleep 100"'
    executor = OutputExecutor(
        command, "foo", timeout=10, stdin=None, stderr=subprocess.PIPE
    ).start()

    assert executor.running() is True
    # foo has been used for start as a banner.
    assert executor.err_output().readline() == "bar\n"
    executor.stop()

    # check proper __str__ and __repr__ rendering:
    assert "OutputExecutor" in repr(executor)
    assert "foo" in str(executor)


def test_executor_waits_for_banner_split_between_reads() -> None:
    """Check if a banner arriving in separate writes is still detected.

    The banner is printed in two chunks, so it lands in two separate reads.
    Unless the tail of the incomplete line is carried over, the first half gets
    consumed unmatched and the banner is never seen again.
    """
    command = 'bash -c "printf foo; sleep 1; printf bar; echo; sleep 100"'
    executor = OutputExecutor(command, "foobar", timeout=10).start()

    assert executor.running() is True
    executor.stop()


def test_executor_dont_start_when_process_exits() -> None:
    """Executor should time out when the process ends without the banner.

    Once the process is gone its output is at end of file, which descriptors
    keep reporting as readable - that must not keep the executor spinning
    instead of honouring its timeout.
    """
    command = 'bash -c "echo foo"'
    executor = OutputExecutor(command, "foobar", timeout=2)
    start = time.time()
    with pytest.raises(TimeoutExpired):
        executor.start()

    assert time.time() - start < 10
    assert executor.running() is False


def test_executor_dont_start() -> None:
    """Executor should not start."""
    command = 'bash -c "sleep 2 && echo foo && echo bar && sleep 100"'
    executor = OutputExecutor(command, "foobar", timeout=3)
    with pytest.raises(TimeoutExpired):
        executor.start()

    assert executor.running() is False
