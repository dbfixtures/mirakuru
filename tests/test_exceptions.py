"""Tests for the executor exception messages."""

from typing import cast

from mirakuru.base import SimpleExecutor
from mirakuru.exceptions import (
    AlreadyRunning,
    ProcessExitedWithError,
    ProcessFinishedWithError,
    TimeoutExpired,
)


class _Executor:
    """Minimal executor stand-in for message formatting."""

    def __init__(self, port: int | None = None) -> None:
        self.port = port

    def __str__(self) -> str:
        return "executor"


def _executor(port: int | None = None) -> SimpleExecutor:
    return cast(SimpleExecutor, _Executor(port))


def test_timeout_expired_owns_its_message() -> None:
    """The timeout message is built by the exception itself."""
    """The timeout message is built by the exception itself."""
    exc = TimeoutExpired(_executor(), timeout=5)

    assert exc.args == ("Executor executor timed out after 5 seconds",)
    assert str(exc) == "Executor executor timed out after 5 seconds"


def test_already_running_owns_its_message_without_port() -> None:
    """Without a configured port the message omits the port hint."""
    """Without a configured port the message omits the port hint."""
    exc = AlreadyRunning(_executor())

    assert str(exc).endswith("terminated or killed.")
    assert "listening on" not in str(exc)


def test_already_running_owns_its_message_with_port() -> None:
    """With a configured port the message explains who may hold it."""
    """With a configured port the message explains who may hold it."""
    exc = AlreadyRunning(_executor(port=8080))

    assert str(exc).endswith("listening on 8080 port.")


def test_process_exited_with_error_owns_its_message() -> None:
    """The exit code is part of the message and the exception state."""
    """The exit code is part of the message and the exception state."""
    exc = ProcessExitedWithError(_executor(), exit_code=12)

    assert exc.exit_code == 12
    assert exc.args == (
        "The process invoked by the executor executor has exited with a non-zero code: 12.",
    )


def test_process_finished_with_error_inherits_the_message() -> None:
    """The stop failure reuses the exited-with-error message."""
    """The stop failure reuses the exited-with-error message."""
    exc = ProcessFinishedWithError(_executor(), exit_code=1)

    assert isinstance(exc, ProcessExitedWithError)
    assert "exited with a non-zero code: 1." in str(exc)
