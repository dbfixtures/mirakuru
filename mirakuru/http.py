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
"""HTTP enabled process executor."""

import re
import socket
from http.client import HTTPConnection, HTTPException
from logging import getLogger
from typing import Any
from urllib.parse import urlencode, urlparse

from mirakuru.tcp import TCPExecutor

LOG = getLogger(__name__)


class HTTPExecutor(TCPExecutor):
    """Http enabled process executor."""

    DEFAULT_PORT = 80
    """Default TCP port for the HTTP protocol."""

    def __init__(
        self,
        command: str | list[str] | tuple[str, ...],
        url: str,
        status: str | int = r"^2\d\d$",
        method: str = "HEAD",
        payload: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize HTTPExecutor executor.

        :param (str, list) command: command to be run by the subprocess
        :param str url: URL that executor checks to verify
            if process has already started.
        :param bool shell: same as the `subprocess.Popen` shell definition
        :param str|int status: HTTP status code(s) that an endpoint must
            return for the executor being considered as running. This argument
            is interpreted as a single status code - e.g. '200' or '404' but
            also it can be a regular expression - e.g. '4..' or '(200|404)'.
            Default: any 2XX HTTP status code.
        :param str method: request method to check status on.
            Defaults to HEAD.
        :param dict payload: Payload to send along the request
        :param dict headers:
        :param int timeout: number of seconds to wait for the process to start
            or stop. If None or False, wait indefinitely.
        :param float sleep: how often to check for start/stop condition
        :param int sig_stop: signal used to stop process run by the executor.
            default is `signal.SIGTERM`
        :param int sig_kill: signal used to kill process run by the executor.
            default is `signal.SIGKILL`

        """
        self.url = urlparse(url)
        """
        An :func:`urlparse.urlparse` representation of an url.

        It'll be used to check process status on.
        """

        if not self.url.hostname:
            raise ValueError("Url provided does not contain hostname")

        port = self.url.port
        if port is None:
            port = self.DEFAULT_PORT

        self.status = str(status)
        self.status_re = re.compile(str(status))
        self.method = method
        self.payload = payload
        self.headers = headers

        super().__init__(command, host=self.url.hostname, port=port, **kwargs)

    def after_start_check(self) -> bool:
        """Check if defined URL returns expected status to a check request."""
        conn = HTTPConnection(self.host, self.port)
        try:
            body = urlencode(self.payload) if self.payload else None
            headers = self.headers if self.headers else {}
            conn.request(
                self.method,
                self.url.path,
                body,
                headers,
            )
            try:
                status = str(conn.getresponse().status)
            finally:
                conn.close()

            if status == self.status or self.status_re.match(status):
                return True
            return False

        except (HTTPException, socket.timeout, socket.error) as ex:
            LOG.debug("Encounter %s while trying to check if service has started.", ex)
            return False
