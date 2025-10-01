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
"""TCP executor definition."""

import socket
from typing import Any

from mirakuru.base import Executor


class TCPExecutor(Executor):
    """TCP-listening process executor.

    Used to start (and wait to actually be running) processes that can accept
    TCP connections.
    """

    def __init__(
        self,
        command: str | list[str] | tuple[str, ...],
        host: str,
        port: int,
        **kwargs: Any,
    ) -> None:
        """Initialize TCPExecutor executor.

        :param (str, list) command: command to be run by the subprocess
        :param str host: host under which process is accessible
        :param int port: port under which process is accessible
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
        self.host = host
        """Host name, process is listening on."""
        self.port = port
        """Port number, process is listening on."""

    def pre_start_check(self) -> bool:
        """Check if process accepts connections.

        .. note::

            Process will be considered started, when it'll be able to accept
            TCP connections as defined in initializer.
        """
        try:
            sock = socket.socket()
            sock.connect((self.host, self.port))
            return True
        except (socket.error, socket.timeout):
            return False
        finally:
            # close socket manually for sake of PyPy
            sock.close()

    def after_start_check(self) -> bool:
        """Check if process accepts connections.

        .. note::

            Process will be considered started, when it'll be able to accept
            TCP connections as defined in initializer.
        """
        return self.pre_start_check()  # we can reuse logic from `pre_start()`
