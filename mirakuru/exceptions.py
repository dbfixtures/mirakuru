"""Mirakuru exceptions."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from mirakuru.base import SimpleExecutor  # pylint:disable=cyclic-import


class ExecutorError(Exception):
    """Base exception for executor failures."""

    _MESSAGE = "Executor {executor} failed"

    def __init__(self, executor: "SimpleExecutor", message: str | None = None) -> None:
        """Exception initialization.

        :param mirakuru.base.SimpleExecutor executor: for which exception
            occurred
        :param str message: exception message, formatted from ``_MESSAGE``
            when not given
        """
        self.executor = executor
        super().__init__(
            message if message is not None else self._MESSAGE.format(executor=executor)
        )


class TimeoutExpired(ExecutorError):
    """Is raised when the timeout expires while starting an executor."""

    _MESSAGE = "Executor {executor} timed out after {timeout} seconds"

    def __init__(self, executor: "SimpleExecutor", timeout: float) -> None:
        """Exception initialization with an extra ``timeout`` argument.

        :param mirakuru.base.SimpleExecutor executor: for which exception
            occurred
        :param int timeout: timeout for which exception occurred
        """
        self.timeout = timeout
        super().__init__(executor, self._MESSAGE.format(executor=executor, timeout=timeout))


class AlreadyRunning(ExecutorError):
    """Is raised when the executor seems to be already running.

    When some other process (not necessary executor) seems to be started with
    same configuration we can't bind to same port.
    """

    _MESSAGE = (
        "Executor {executor} seems to be already running. "
        "It looks like the previous executor process hasn't been "
        "terminated or killed."
    )
    _PORT_MESSAGE = (
        " Also there might be some completely different service listening on {port} port."
    )

    def __init__(self, executor: "SimpleExecutor") -> None:
        """Exception initialization, adding the port hint when one is configured.

        :param mirakuru.base.SimpleExecutor executor: for which exception
            occurred
        """
        message = self._MESSAGE.format(executor=executor)
        port = getattr(executor, "port", None)
        if port is not None:
            message += self._PORT_MESSAGE.format(port=port)
        super().__init__(executor, message)


class ProcessExitedWithError(ExecutorError):
    """Raised when the process invoked by the executor returns a non-zero code.

    We allow the process to exit with zero because we support daemonizing
    subprocesses. We assume that when double-forking, the parent process will
    exit with 0 in case of successful daemonization.
    """

    _MESSAGE = (
        "The process invoked by the {executor} executor has "
        "exited with a non-zero code: {exit_code}."
    )

    def __init__(self, executor: "SimpleExecutor", exit_code: int) -> None:
        """Exception initialization with an extra ``exit_code`` argument.

        :param mirakuru.base.SimpleExecutor executor: for which exception
            occurred
        :param int exit_code: code the subprocess exited with
        """
        self.exit_code = exit_code
        super().__init__(executor, self._MESSAGE.format(executor=executor, exit_code=exit_code))


class ProcessFinishedWithError(ProcessExitedWithError):
    """Raised when the process invoked by the executor fails when stopping.

    When a process is stopped, it should shut down cleanly and return zero as
    exit code. When is returns a non-zero exit code, this exception is raised.
    """
