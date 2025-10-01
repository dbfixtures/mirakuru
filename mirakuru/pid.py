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
"""Pid executor definition."""

import os.path
from typing import Any

from mirakuru.base import Executor


class PidExecutor(Executor):
    """File existence checking process executor.

    Used to start processes that create pid files (or any other for that
    matter). Starts the given process and waits for the given file to be
    created.
    """

    def __init__(
        self,
        command: str | list[str] | tuple[str, ...],
        filename: str,
        **kwargs: Any,
    ) -> None:
        """Initialize the PidExecutor executor.

        If the filename is empty, a ValueError is thrown.

        :param (str, list) command: command to be run by the subprocess
        :param str filename: the file which is to exist
        :param bool shell: same as the `subprocess.Popen` shell definition
        :param int timeout: number of seconds to wait for the process to start
            or stop. If None or False, wait indefinitely.
        :param float sleep: how often to check for start/stop condition
        :param int sig_stop: signal used to stop process run by the executor.
            default is `signal.SIGTERM`
        :param int sig_kill: signal used to kill process run by the executor.
            default is `signal.SIGKILL` (`signal.SIGTERM` on Windows)

        :raises: ValueError

        """
        super().__init__(command, **kwargs)
        if not filename:
            raise ValueError("filename must be defined")
        self.filename = filename
        """the name of the file which the process is to create."""

    def pre_start_check(self) -> bool:
        """Check if the specified file has been created.

        .. note::

            The process will be considered started when it will have created
            the specified file as defined in the initializer.
        """
        return os.path.isfile(self.filename)

    def after_start_check(self) -> bool:
        """Check if the process has created the specified file.

        .. note::

            The process will be considered started when it will have created
            the specified file as defined in the initializer.
        """
        return self.pre_start_check()  # we can reuse logic from `pre_start()`
