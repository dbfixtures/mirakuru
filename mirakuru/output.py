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
        # Also keep a bytes-compiled regex to operate on raw peeked bytes.
        try:
            self._banner_bytes = re.compile(self._banner.pattern.encode("utf-8"))
        except Exception:
            # Fallback: a simple utf-8 encode of provided banner string
            self._banner_bytes = re.compile(str(banner).encode("utf-8"))
        if not any((self._stdout, self._stderr)):
            raise TypeError("At least one of stdout or stderr has to be initialized")

    def start(self: OutputExecutorType) -> OutputExecutorType:
        """Start the process.

        .. note::

            Process will be considered started when a defined banner appears
            in the process output.
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
                while len(polls) > 0:
                    poll_and_output = polls.pop()
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

    def _consume_until_banner_or_block(self, output: IO[Any]) -> tuple[bool, bool]:
        """Consume available data from a ready stream and check for banner.

        Returns a pair (found, should_break):
        - found: banner was detected and consumed up to end-of-line.
        - should_break: no more data immediately available for this descriptor,
          so the caller's inner draining loop should break.
        """
        raw = getattr(output, "buffer", None)
        if raw is None:
            # Fallback to safe line reads on text wrappers
            line = output.readline()
            if not line:
                return False, True
            if self._banner.match(line):
                return True, True
            return False, False
        preview = raw.peek(65536)  # 64KB
        if not preview:
            return False, True
        m = self._banner_bytes.search(preview)
        if m is None:
            to_read = min(len(preview), 8192)  # 8KB
            _ = raw.read(to_read)
            return False, False
        nl_pos = preview.find(b"\n", m.end())
        if nl_pos == -1:
            _ = raw.read(len(preview))
            return False, False
        _ = raw.read(nl_pos + 1)
        return True, True

    def _wait_for_darwin_output(self, *fds: IO[Any] | None) -> bool:
        """Select an implementation to be used on macOS using select().

        Drain all immediately available data in small chunks from ready
        descriptors and look for the banner using regex.search on a rolling
        buffer. This avoids blocking on TextIOWrapper.readline() with partial
        data and prevents pipe backpressure under heavy pre-banner output.
        """
        # Filter out Nones defensively
        valid_fds = tuple(fd for fd in fds if fd is not None)
        if not valid_fds:
            return False

        found = False
        # Keep draining while there is data immediately available.
        while True:
            rlist, _, _ = select.select(valid_fds, [], [], 0)
            if not rlist:
                break
            for output in rlist:
                while True:
                    rready, _, _ = select.select([output], [], [], 0)
                    if not rready:
                        break
                    found, should_break = self._consume_until_banner_or_block(output)
                    if found:
                        return True
                    if should_break:
                        break
                    # else continue draining
        return found

    def _wait_for_output(self, *polls: tuple["select.poll", IO[Any]]) -> bool:
        """Check if output matches banner.

        Drain as much data as available from ready descriptors in bursts using
        non-blocking chunked reads to avoid stalling on text line buffering.
        Returns True as soon as the banner is detected using regex.search().

        .. warning::
            Waiting for I/O completion. It does not work on Windows. Sorry.
        """
        found = False
        any_ready = True
        # Keep draining while something is ready; exit when nothing is immediately ready.
        while any_ready:
            any_ready = False
            for p, output in polls:
                # Poll for readiness; when ready, drain in a controlled manner.
                while p.poll(0):
                    any_ready = True
                    found, should_break = self._consume_until_banner_or_block(output)
                    if found:
                        return True
                    if should_break:
                        break
                    # else continue draining
            # loop continues if any_ready set
        return found
