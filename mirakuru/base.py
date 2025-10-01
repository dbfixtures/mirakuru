# Copyright (C) 2014 by Clearcode <http://clearcode.cc>
# and associates (see AUTHORS).

# This file is part of mirakuru.

# mirakuru is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# mirakuru is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.

# You should have received a copy of the GNU Lesser General Public License
# along with mirakuru.  If not, see <http://www.gnu.org/licenses/>.
"""Executor with the core functionality."""

import atexit
import errno
import logging
import os
import platform
import shlex
import signal
import subprocess
import time
import uuid
from contextlib import contextmanager
from types import TracebackType
from typing import (
    IO,
    Any,
    Callable,
    Iterator,
    Type,
    TypeVar,
)

from mirakuru.base_env import processes_with_env
from mirakuru.compat import SIGKILL
from mirakuru.exceptions import (
    AlreadyRunning,
    ProcessExitedWithError,
    ProcessFinishedWithError,
    TimeoutExpired,
)

LOG = logging.getLogger(__name__)

ENV_UUID = "mirakuru_uuid"
"""
Name of the environment variable used by mirakuru to mark its subprocesses.
"""

IGNORED_ERROR_CODES = [errno.ESRCH]
if platform.system() == "Darwin":
    IGNORED_ERROR_CODES = [errno.ESRCH, errno.EPERM]

# Type variables used for self in functions returning self, so it's correctly
# typed in derived classes.
SimpleExecutorType = TypeVar("SimpleExecutorType", bound="SimpleExecutor")
ExecutorType = TypeVar("ExecutorType", bound="Executor")


@atexit.register
def cleanup_subprocesses() -> None:
    """On python exit: find possibly running subprocesses and kill them."""
    # atexit functions tends to loose global imports sometimes so reimport
    # everything what is needed again here:
    import errno
    import os

    from mirakuru.base_env import processes_with_env
    from mirakuru.compat import SIGKILL

    pids = processes_with_env(ENV_UUID, str(os.getpid()))
    for pid in pids:
        try:
            os.kill(pid, SIGKILL)
        except OSError as err:
            if err.errno != errno.ESRCH:
                print("Can not kill the", pid, "leaked process", err)


class SimpleExecutor:  # pylint:disable=too-many-instance-attributes
    """Simple subprocess executor with start/stop/kill functionality."""

    def __init__(  # pylint:disable=too-many-arguments
        self,
        command: str | list[str] | tuple[str, ...],
        cwd: str | None = None,
        shell: bool = False,
        timeout: int | float = 3600,
        sleep: float = 0.1,
        stop_signal: int = signal.SIGTERM,
        kill_signal: int = SIGKILL,
        expected_returncode: int | None = None,
        envvars: dict[str, str] | None = None,
        stdin: None | int | IO[Any] = subprocess.PIPE,
        stdout: None | int | IO[Any] = subprocess.PIPE,
        stderr: None | int | IO[Any] = None,
    ) -> None:
        """Initialize executor.

        :param (str, list) command: command to be run by the subprocess
        :param str cwd: current working directory to be set for executor
        :param bool shell: same as the `subprocess.Popen` shell definition.
            On Windows always set to True.
        :param int timeout: number of seconds to wait for the process to start
            or stop.
        :param float sleep: how often to check for start/stop condition
        :param int stop_signal: signal used to stop process run by the executor.
            default is `signal.SIGTERM`
        :param int kill_signal: signal used to kill process run by the executor.
            default is `signal.SIGKILL` (`signal.SIGTERM` on Windows)
        :param int expected_returncode: expected exit code.
            default is None which means, Executor will determine a POSIX
            compatible return code based on signal sent.
        :param dict envvars: Additional environment variables
        :param int stdin: file descriptor for stdin
        :param int stdout: file descriptor for stdout
        :param int stderr: file descriptor for stderr

        .. note::

            **timeout** set for an executor is valid for all the level of waits
            on the way up. That means that if some more advanced executor
            establishes the timeout to 10 seconds and it will take 5 seconds
            for the first check, second check will only have 5 seconds left.

            Your executor will raise an exception if something goes wrong
            during this time. The default value of timeout is ``None``, so it
            is a good practice to set this.

        """
        if isinstance(command, (list, tuple)):
            self.command = " ".join((shlex.quote(c) for c in command))
            """Command that the executor runs."""
            self.command_parts = command
        else:
            self.command = command
            self.command_parts = shlex.split(command)

        self._cwd = cwd
        self._shell = True
        if platform.system() != "Windows":
            self._shell = shell

        self._timeout = timeout
        self._sleep = sleep
        self._stop_signal = stop_signal
        self._kill_signal = kill_signal
        self._expected_returncode = expected_returncode
        self._envvars = envvars or {}

        self._stdin = stdin
        self._stdout = stdout
        self._stderr = stderr

        self._endtime: float | None = None
        self.process: subprocess.Popen | None = None
        """A :class:`subprocess.Popen` instance once process is started."""

        self._uuid = f"{os.getpid()}:{uuid.uuid4()}"

    def __enter__(self: SimpleExecutorType) -> SimpleExecutorType:
        """Enter context manager starting the subprocess.

        :returns: itself
        :rtype: SimpleExecutor
        """
        return self.start()

    def __exit__(
        self,
        exc_type: Type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Exit context manager stopping the subprocess."""
        self.stop()

    def running(self) -> bool:
        """Check if executor is running.

        :returns: True if process is running, False otherwise
        :rtype: bool
        """
        if self.process is None:
            LOG.debug("There is no process running!")
            return False
        return self.process.poll() is None

    @property
    def envvars(self) -> dict[str, str]:
        """Combines required environment variables with os.environ and mirakuru_uuid."""
        envs = os.environ.copy()
        envs.update(self._envvars)
        # Trick with marking subprocesses with an environment variable.
        #
        # There is no easy way to recognize all subprocesses that were
        # spawned during lifetime of a certain subprocess so mirakuru does
        # this hack in order to mark who was the original parent. Even if
        # some subprocess got daemonized or changed original process group
        # mirakuru will be able to find it by this environment variable.
        #
        # There may be a situation when some subprocess will abandon
        # original envs from parents and then it won't be later found.
        envs[ENV_UUID] = self._uuid
        return envs

    @property
    def _popen_kwargs(self) -> dict[str, Any]:
        """Get kwargs for the process instance.

        .. note::
            We want to open ``stdin``, ``stdout`` and ``stderr`` as text
            streams in universal newlines mode, so we have to set
            ``universal_newlines`` to ``True``.

        :return:
        """
        kwargs: dict[str, Any] = {}

        if self._stdin:
            kwargs["stdin"] = self._stdin
        if self._stdout:
            kwargs["stdout"] = self._stdout
        if self._stderr:
            kwargs["stderr"] = self._stderr
        kwargs["universal_newlines"] = True

        kwargs["shell"] = self._shell
        kwargs["env"] = self.envvars
        kwargs["cwd"] = self._cwd
        if platform.system() != "Windows":
            kwargs["preexec_fn"] = os.setsid

        return kwargs

    def start(self: SimpleExecutorType) -> SimpleExecutorType:
        """Start defined process.

        After process gets started, timeout countdown begins as well.

        :returns: itself
        :rtype: SimpleExecutor
        """
        if self.process is None:
            command: str | list[str] | tuple[str, ...] = self.command
            if not self._shell:
                command = self.command_parts
            LOG.debug("Starting process: %s", command)
            self.process = subprocess.Popen(command, **self._popen_kwargs)

        self._set_timeout()
        return self

    def _set_timeout(self) -> None:
        """Set timeout for possible wait."""
        self._endtime = time.time() + self._timeout

    def _clear_process(self) -> None:
        """Close stdin/stdout of subprocess.

        It is required because of ResourceWarning in Python 3.
        """
        if self.process:
            self.process.__exit__(None, None, None)
            self.process = None

        self._endtime = None

    def _kill_all_kids(self, sig: int) -> set[int]:
        """Kill all subprocesses (and its subprocesses) that executor started.

        This function tries to kill all leftovers in process tree that current
        executor may have left. It uses environment variable to recognise if
        process have origin in this Executor so it does not give 100 % and
        some daemons fired by subprocess may still be running.

        :param int sig: signal used to stop process run by executor.
        :return: process ids (pids) of killed processes
        :rtype: set
        """
        pids = processes_with_env(ENV_UUID, self._uuid)
        for pid in pids:
            LOG.debug("Killing process %d ...", pid)
            try:
                os.kill(pid, sig)
            except OSError as err:
                if err.errno in IGNORED_ERROR_CODES:
                    # the process has died before we tried to kill it.
                    pass
                else:
                    raise
            LOG.debug("Killed process %d.", pid)
        return pids

    def stop(
        self: SimpleExecutorType,
        stop_signal: int | None = None,
        expected_returncode: int | None = None,
    ) -> SimpleExecutorType:
        """Stop process running.

        Wait 10 seconds for the process to end, then just kill it.

        :param int stop_signal: signal used to stop process run by executor.
            None for default.
        :param int expected_returncode: expected exit code.
            None for default - POSIX compatible behaviour.
        :returns: self
        :rtype: SimpleExecutor

        .. note::

            When gathering coverage for the subprocess in tests,
            you have to allow subprocesses to end gracefully.
        """
        if self.process is None:
            return self

        if stop_signal is None:
            stop_signal = self._stop_signal

        try:
            os.killpg(self.process.pid, stop_signal)
        except OSError as err:
            if err.errno in IGNORED_ERROR_CODES:
                pass
            else:
                raise

        def process_stopped() -> bool:
            """Return True only only when self.process is not running."""
            return self.running() is False

        self._set_timeout()
        try:
            self.wait_for(process_stopped)
        except TimeoutExpired:
            # at this moment, process got killed,
            pass

        if self.process is None:
            # the process has already been force killed and cleaned up by the
            # `wait_for` above.
            return self  # type: ignore[unreachable]
        self._kill_all_kids(stop_signal)
        exit_code = self.process.wait()
        self._clear_process()

        if expected_returncode is None:
            expected_returncode = self._expected_returncode
        if expected_returncode is None:
            # Assume a POSIX approach where sending a SIGNAL means
            # that the process should exist with -SIGNAL exit code.
            # https://docs.python.org/3/library/subprocess.html#subprocess.Popen.returncode
            expected_returncode = -stop_signal

        if exit_code and exit_code != expected_returncode:
            raise ProcessFinishedWithError(self, exit_code)

        return self

    @contextmanager
    def stopped(self: SimpleExecutorType) -> Iterator[SimpleExecutorType]:
        """Stop process for given context and starts it afterwards.

        Allows for easier writing resistance integration tests whenever one of
        the service fails.
        :yields: itself
        :rtype: SimpleExecutor
        """
        if self.running():
            self.stop()
            yield self
            self.start()

    def kill(
        self: SimpleExecutorType, wait: bool = True, sig: int | None = None
    ) -> SimpleExecutorType:
        """Kill the process if running.

        :param bool wait: set to `True` to wait for the process to end,
            or False, to simply proceed after sending signal.
        :param int sig: signal used to kill process run by the executor.
            None by default.
        :returns: itself
        :rtype: SimpleExecutor
        """
        if sig is None:
            sig = self._kill_signal
        if self.process and self.running():
            os.killpg(self.process.pid, sig)
            if wait:
                self.process.wait()

        self._kill_all_kids(sig)
        self._clear_process()
        return self

    def output(self) -> IO[Any] | None:
        """Return subprocess output."""
        if self.process is not None:
            return self.process.stdout
        return None  # pragma: no cover

    def err_output(self) -> IO[Any] | None:
        """Return subprocess stderr."""
        if self.process is not None:
            return self.process.stderr
        return None  # pragma: no cover

    def wait_for(self: SimpleExecutorType, wait_for: Callable[[], bool]) -> SimpleExecutorType:
        """Wait for callback to return True.

        Simply returns if wait_for condition has been met,
        raises TimeoutExpired otherwise and kills the process.

        :param callback wait_for: callback to call
        :raises: mirakuru.exceptions.TimeoutExpired
        :returns: itself
        :rtype: SimpleExecutor
        """
        while self.check_timeout():
            if wait_for():
                return self
            time.sleep(self._sleep)

        self.kill()
        raise TimeoutExpired(self, timeout=self._timeout)

    def check_timeout(self) -> bool:
        """Check if timeout has expired.

        Returns True if there is no timeout set or the timeout has not expired.
        Kills the process and raises TimeoutExpired exception otherwise.

        This method should be used in while loops waiting for some data.

        :return: True if timeout expired, False if not
        :rtype: bool
        """
        return self._endtime is None or time.time() <= self._endtime

    def __del__(self) -> None:
        """Cleanup subprocesses created during Executor lifetime."""
        try:
            if self.process:
                self.kill()
        except Exception:  # pragma: no cover
            print("*" * 80)
            print("Exception while deleting Executor. It is strongly suggested that you use")
            print("it as a context manager instead.")
            print("*" * 80)
            raise

    def __repr__(self) -> str:
        """Return unambiguous executor representation."""
        command = self.command
        if len(command) > 10:
            command = command[:10] + "..."
        module = self.__class__.__module__
        executor = self.__class__.__name__
        return f'<{module}.{executor}: "{command}" {hex(id(self))}>'

    def __str__(self) -> str:
        """Return readable executor representation."""
        module = self.__class__.__module__
        executor = self.__class__.__name__
        return f'<{module}.{executor}: "{self.command}" {hex(id(self))}>'


class Executor(SimpleExecutor):
    """Base class for executors with a pre- and after-start checks."""

    def pre_start_check(self) -> bool:
        """Check process before the start of executor.

        Should be overridden in order to return True when some other
        executor (or process) has already started with the same configuration.
        :rtype: bool
        """
        raise NotImplementedError

    def start(self: ExecutorType) -> ExecutorType:
        """Start executor with additional checks.

        Checks if previous executor isn't running then start process
        (executor) and wait until it's started.
        :returns: itself
        :rtype: Executor
        """
        if self.pre_start_check():
            # Some other executor (or process) is running with same config:
            raise AlreadyRunning(self)

        super().start()

        self.wait_for(self.check_subprocess)
        return self

    def check_subprocess(self) -> bool:
        """Make sure the process didn't exit with an error and run the checks.

        :rtype: bool
        :return: the actual check status or False before starting the process
        :raise ProcessExitedWithError: when the main process exits with
            an error
        """
        if self.process is None:  # pragma: no cover
            # No process was started.
            return False
        exit_code = self.process.poll()
        if exit_code is not None and exit_code != 0:
            # The main process exited with an error. Clean up the children
            # if any.
            self._kill_all_kids(self._kill_signal)
            self._clear_process()
            raise ProcessExitedWithError(self, exit_code)

        return self.after_start_check()

    def after_start_check(self) -> bool:
        """Check process after the start of executor.

        Should be overridden in order to return boolean value if executor
        can be treated as started.
        :rtype: bool
        """
        raise NotImplementedError
