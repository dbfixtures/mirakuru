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
"""Executor that awaits for appearance of a predefined banner in output."""

import platform
import re
import select
from typing import IO, Any, TypeVar

from mirakuru.base import SimpleExecutor

IS_DARWIN = platform.system() == "Darwin"


OutputExecutorType = TypeVar("OutputExecutorType", bound="OutputExecutor")


class OutputExecutor(SimpleExecutor):
    """Executor that awaits for string output being present in output."""

    def __init__(
        self,
        command: str | list[str] | tuple[str, ...],
        banner: str,
        **kwargs: Any,
    ) -> None:
        """Initialize OutputExecutor executor.

        :param (str, list) command: command to be run by the subprocess
        :param str banner: string that has to appear in process output -
            should compile to regular expression.
        :param bool shell: same as the `subprocess.Popen` shell definition
        :param int timeout: number of seconds to wait for the process to start
            or stop. If None or False, wait indefinitely.
        :param float sleep: how often to check for start/stop condition
        :param int sig_stop: signal used to stop process run by the executor.
            default is `signal.SIGTERM`
        :param int sig_kill: signal used to kill process run by the executor.
            default is `signal.SIGKILL` (`signal.SIGTERM` on Windows)

        """
        super().__init__(command, **kwargs)
        self._banner = re.compile(banner)
        if not any((self._stdout, self._stderr)):
            raise TypeError("At least one of stdout or stderr has to be initialized")

    def start(self: OutputExecutorType) -> OutputExecutorType:
        """Start process.

        :returns: itself
        :rtype: OutputExecutor

        .. note::

            Process will be considered started, when defined banner will appear
            in process output.
        """
        super().start()

        if not IS_DARWIN:
            polls: list[tuple[select.poll, IO[Any]]] = []
            for output_handle, output_method in (
                (self._stdout, self.output),
                (self._stderr, self.err_output),
            ):
                if output_handle is not None:
                    # get a polling object
                    std_poll = select.poll()

                    output_file = output_method()
                    if output_file is None:
                        raise ValueError("The process is started but the output file is None")
                    # register a file descriptor
                    # POLLIN because we will wait for data to read
                    std_poll.register(output_file, select.POLLIN)
                    polls.append((std_poll, output_file))

            try:

                def await_for_output() -> bool:
                    return self._wait_for_output(*polls)

                self.wait_for(await_for_output)

                for poll, output in polls:
                    # unregister the file descriptor
                    # and delete the polling object
                    poll.unregister(output)
            finally:
                for poll_and_output in polls:
                    del poll_and_output
        else:
            outputs = []
            for output_handle, output_method in (
                (self._stdout, self.output),
                (self._stderr, self.err_output),
            ):
                if output_handle is not None:
                    outputs.append(output_method())

            def await_for_output() -> bool:
                return self._wait_for_darwin_output(*outputs)

            self.wait_for(await_for_output)

        return self

    def _wait_for_darwin_output(self, *fds: IO[Any] | None) -> bool:
        """Select implementation to be used on MacOSX."""
        rlist, _, _ = select.select(fds, [], [], 0)
        for output in rlist:
            line = output.readline()
            if self._banner.match(line):
                return True
        return False

    def _wait_for_output(self, *polls: tuple["select.poll", IO[Any]]) -> bool:
        """Check if output matches banner.

        .. warning::
            Waiting for I/O completion. It does not work on Windows. Sorry.
        """
        for poll, output in polls:
            # Here we should get an empty list or list with a tuple
            # [(fd, event)]. When we get list with a tuple we can use readline
            # method on the file descriptor.
            poll_result = poll.poll(0)

            if poll_result:
                line = output.readline()
                if self._banner.match(line):
                    return True

        return False
