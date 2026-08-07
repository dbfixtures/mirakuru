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

_KB = 1024

PEEK_SIZE = _KB * 64
"""How many bytes to look at in a single peek into a stream's buffer."""

MAX_CARRY_OVER = _KB * 64
"""Upper bound on the number of bytes carried over between reads.

Carrying data over is what allows a banner that got split across two reads
to be matched. See :meth:`OutputExecutor._consume_chunk`.
"""

DRAIN_TIMEOUT = 50
"""For how long (in milliseconds) to keep waiting for more data.

Applies while a stream is actively producing output, before control is handed
back to :meth:`mirakuru.base.SimpleExecutor.wait_for`.
"""


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
        # Per descriptor remainder of the last, not yet terminated line that
        # has already been consumed. See `_consume_chunk`.
        self._carry_over: dict[int, bytes] = {}
        if not any((self._stdout, self._stderr)):
            raise TypeError("At least one of stdout or stderr has to be initialized")

    def start(self: OutputExecutorType) -> OutputExecutorType:
        """Start the process.

        .. note::

            Process will be considered started when a defined banner appears
            in the process output.
        """
        super().start()
        self._carry_over.clear()

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

    def _consume_chunk(self, output: IO[Any]) -> tuple[bool, bool]:
        """Consume one chunk of a ready stream's data and check for banner.

        Iterating is up to the caller. Must only be called for a descriptor that
        has been reported readable, as peeking into an empty buffer would block.

        Returns a pair (found, exhausted):
        - found: banner was detected and consumed up to end-of-line.
        - exhausted: nothing has been consumed, either because no more data is
          immediately available or because the stream is at its end, so the
          caller's inner draining loop should break. Only meaningful when the
          banner has not been found.
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
        preview = raw.peek(PEEK_SIZE)
        if not preview:
            return False, True
        # Prepend the tail of the previously consumed line, so that a banner
        # spanning two reads is matched instead of being silently dropped.
        carry_over = self._carry_over.get(output.fileno(), b"")
        data = carry_over + preview

        match = self._banner_bytes.search(data)
        newline = -1 if match is None else data.find(b"\n", match.end())
        if newline == -1:
            # Either the banner has not shown up yet, or it did but its line is
            # not terminated yet - in which case everything peeked is part of
            # that unfinished line. Both cases are safe to consume as a whole,
            # keeping whatever follows the last newline for the next round.
            _ = raw.read(len(preview))
            tail = data[data.rfind(b"\n") + 1 :]
            self._carry_over[output.fileno()] = tail[-MAX_CARRY_OVER:]
            return False, False
        # The carry over never holds a newline, so the one found above is part
        # of the peeked data. Stop right after it, leaving everything the
        # process wrote past the banner for the caller to read.
        _ = raw.read(newline - len(carry_over) + 1)
        return True, True

    def _wait_for_darwin_output(self, *fds: IO[Any] | None) -> bool:
        """Look for the banner using select(), on macOS.

        Drains exactly like :meth:`_wait_for_output` does, only driven by
        select(), because on macOS the presence of `select.poll` depends on the
        compiler Python was built with.
        """
        # Filter out Nones defensively
        valid_fds = tuple(fd for fd in fds if fd is not None)
        if not valid_fds:
            return False

        drained = False
        # Keep draining while there is data available.
        while True:
            consumed = False
            rlist, _, _ = select.select(valid_fds, [], [], DRAIN_TIMEOUT / 1000 if drained else 0)
            if not rlist:
                return False
            for output in rlist:
                while True:
                    found, exhausted = self._consume_chunk(output)
                    if found:
                        return True
                    if exhausted:
                        break
                    drained = consumed = True
                    if not self.check_timeout():
                        # Do not let a process that never stops writing keep us
                        # here past the executor's timeout.
                        return False
                    rready, _, _ = select.select([output], [], [], DRAIN_TIMEOUT / 1000)
                    if not rready:
                        break
            if not consumed:
                # Descriptors are readable but yield nothing, they are done.
                return False

    def _wait_for_output(self, *polls: tuple["select.poll", IO[Any]]) -> bool:
        """Look for the banner using poll(), on every platform but macOS.

        Drains the ready descriptors chunk by chunk, returning True as soon as
        regex.search() spots the banner. Chunked reads keep a partial line from
        stalling on TextIOWrapper.readline() and keep heavy pre-banner output
        from filling up the pipe.

        .. warning::
            Waiting for I/O completion. It does not work on Windows. Sorry.
        """
        drained = False
        # Keep draining while something is ready; exit when the streams go quiet.
        while True:
            consumed = False
            for p, output in polls:
                # Poll for readiness; when ready, drain in a controlled manner.
                # Once data started flowing, wait a moment for more rather than
                # returning right away: every return here costs a full
                # `wait_for` sleep cycle, which throttles draining to about one
                # pipe buffer per sleep interval.
                while p.poll(DRAIN_TIMEOUT if drained else 0):
                    found, exhausted = self._consume_chunk(output)
                    if found:
                        return True
                    if exhausted:
                        break
                    drained = consumed = True
                    if not self.check_timeout():
                        # Do not let a process that never stops writing keep us
                        # here past the executor's timeout.
                        return False
            if not consumed:
                # Descriptors are quiet or yield nothing, hand back control.
                return False
