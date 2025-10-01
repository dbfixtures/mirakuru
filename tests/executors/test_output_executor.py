# mypy: no-strict-optional
"""Output executor test."""

import subprocess

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


def test_executor_dont_start() -> None:
    """Executor should not start."""
    command = 'bash -c "sleep 2 && echo foo && echo bar && sleep 100"'
    executor = OutputExecutor(command, "foobar", timeout=3)
    with pytest.raises(TimeoutExpired):
        executor.start()

    assert executor.running() is False
