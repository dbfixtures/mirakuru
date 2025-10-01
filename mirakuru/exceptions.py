"""Mirakuru exceptions."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from mirakuru.base import SimpleExecutor  # pylint:disable=cyclic-import


class ExecutorError(Exception):
    """Base exception for executor failures."""

    def __init__(self, executor: "SimpleExecutor") -> None:
        """Exception initialization.

        :param mirakuru.base.SimpleExecutor executor: for which exception
            occurred
        """
        super().__init__(self)
        self.executor = executor


class TimeoutExpired(ExecutorError):
    """Is raised when the timeout expires while starting an executor."""

    def __init__(self, executor: "SimpleExecutor", timeout: int | float) -> None:
        """Exception initialization with an extra ``timeout`` argument.

        :param mirakuru.base.SimpleExecutor executor: for which exception
            occurred
        :param int timeout: timeout for which exception occurred
        """
        super().__init__(executor)
        self.timeout = timeout

    def __str__(self) -> str:
        """Return Exception's string representation.

        :returns: string representation
        :rtype: str
        """
        return f"Executor {self.executor} timed out after {self.timeout} seconds"


class AlreadyRunning(ExecutorError):
    """Is raised when the executor seems to be already running.

    When some other process (not necessary executor) seems to be started with
    same configuration we can't bind to same port.
    """

    def __str__(self) -> str:
        """Return Exception's string representation.

        :returns: string representation
        :rtype: str
        """
        port = getattr(self.executor, "port")
        return (
            f"Executor {self.executor} seems to be already running. "
            f"It looks like the previous executor process hasn't been "
            f"terminated or killed."
            + (
                ""
                if port is None
                else f" Also there might be some completely "
                f"different service listening on {port} port."
            )
        )


class ProcessExitedWithError(ExecutorError):
    """Raised when the process invoked by the executor returns a non-zero code.

    We allow the process to exit with zero because we support daemonizing
    subprocesses. We assume that when double-forking, the parent process will
    exit with 0 in case of successful daemonization.
    """

    def __init__(self, executor: "SimpleExecutor", exit_code: int) -> None:
        """Exception initialization with an extra ``exit_code`` argument.

        :param mirakuru.base.SimpleExecutor executor: for which exception
            occurred
        :param int exit_code: code the subprocess exited with
        """
        super().__init__(executor)
        self.exit_code = exit_code

    def __str__(self) -> str:
        """Return Exception's string representation.

        :returns: string representation
        :rtype: str
        """
        return (
            f"The process invoked by the {self.executor} executor has "
            f"exited with a non-zero code: {self.exit_code}."
        )


class ProcessFinishedWithError(ProcessExitedWithError):
    """Raised when the process invoked by the executor fails when stopping.

    When a process is stopped, it should shut down cleanly and return zero as
    exit code. When is returns a non-zero exit code, this exception is raised.
    """
