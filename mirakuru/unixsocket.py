# Copyright (C) 2019 by Clearcode <http://clearcode.cc>
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
"""TCP Socket executor definition."""

import logging
import socket
from typing import Any, List, Tuple, Union

from mirakuru import Executor

LOG = logging.getLogger(__name__)


class UnixSocketExecutor(Executor):
    """Unixsocket listening process executor.

    Used to start (and wait to actually be running) processes that can accept
    stream Unix socket connections.
    """

    def __init__(
        self,
        command: Union[str, List[str], Tuple[str, ...]],
        socket_name: str,
        **kwargs: Any,
    ) -> None:
        """Initialize UnixSocketExecutor executor.

        :param (str, list) command: command to be run by the subprocess
        :param str socket_name: unix socket path
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
        self.socket = socket_name

    def pre_start_check(self) -> bool:
        """Check if process accepts connections.

        .. note::

            Process will be considered started, when it'll be able to accept
            Unix Socket connections as defined in initializer.
        """
        exec_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            exec_sock.connect(self.socket)
            return True
        except socket.error as msg:
            LOG.debug("Can not connect to socket: %s", msg)
            return False
        finally:
            # close socket manually for sake of PyPy
            exec_sock.close()

    def after_start_check(self) -> bool:
        """Check if process accepts connections.

        .. note::

            Process will be considered started, when it'll be able to accept
            Unix Socket connections as defined in initializer.
        """
        return self.pre_start_check()  # we can reuse logic from `pre_start()`
