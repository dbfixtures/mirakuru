"""HTTP server that responses with delays used for tests.

Example usage:

    python tests/slow_server.py [HOST:PORT]

        - run HTTP Server, HOST and PORT are optional

    python tests/slow_server.py [HOST:PORT] True

        - run IMMORTAL server (stopping process only by SIGKILL)

"""

import ast
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

sys.path.append(os.getcwd())

from tests.signals import block_signals  # noqa: E402

HANG_TIME = 3600
"""Seconds the hanging handler sits on a request, i.e. forever as far as a test cares."""


class SlowServerHandler(BaseHTTPRequestHandler):
    """Slow server handler."""

    timeout = 2
    endtime = None

    def do_GET(self) -> None:  # pylint:disable=invalid-name
        """Serve GET request."""
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Hi. I am very slow.")

    def do_HEAD(self) -> None:  # pylint:disable=invalid-name
        """Serve HEAD request.

        but count to wait and return 500 response if wait time not exceeded
        due to the fact that HTTPServer will hang waiting for response
        to return otherwise if none response will be returned.
        """
        self.timeout_status()
        self.end_headers()

    def timeout_status(self) -> None:
        """Set proper response status based on timeout."""
        if self.count_timeout():
            self.send_response(200)
        else:
            self.send_response(500)

    def count_timeout(self) -> bool:  # pylint: disable=no-self-use
        """Count down the timeout time."""
        if SlowServerHandler.endtime is None:
            SlowServerHandler.endtime = time.time() + SlowServerHandler.timeout
        return time.time() >= SlowServerHandler.endtime


class SlowGetServerHandler(SlowServerHandler):
    """Responds only on GET after a while."""

    def do_GET(self) -> None:  # pylint:disable=invalid-name
        """Serve GET request."""
        self.timeout_status()
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Hi. I am very slow.")

    def do_HEAD(self) -> None:  # pylint:disable=invalid-name
        """Serve HEAD request."""
        self.send_response(500)
        self.end_headers()


class SlowPostServerHandler(SlowServerHandler):
    """Responds only on POST after a while."""

    def do_POST(self) -> None:  # pylint:disable=invalid-name
        """Serve POST request."""
        self.timeout_status()
        self.end_headers()
        self.wfile.write(b"Hi. I am very slow.")

    def do_HEAD(self) -> None:  # pylint:disable=invalid-name
        """Serve HEAD request."""
        self.send_response(500)
        self.end_headers()


class SlowPostKeyServerHandler(SlowServerHandler):
    """Responds only on POST after a while."""

    def do_POST(self) -> None:  # pylint:disable=invalid-name
        """Serve POST request."""
        content_len = int(self.headers["Content-Length"])
        post_body = self.rfile.read(content_len)
        form = parse_qs(post_body)
        if form.get(b"key") == [b"hole"]:
            self.timeout_status()
        else:
            self.send_response(500)
        self.end_headers()
        self.wfile.write(b"Hi. I am very slow.")

    def do_HEAD(self) -> None:  # pylint:disable=invalid-name
        """Serve HEAD request."""
        self.send_response(500)
        self.end_headers()


class HangingServerHandler(BaseHTTPRequestHandler):
    """Accept the connection and then never answer it.

    Mimics a process taking forever to respond, hanging from the test point of view.
    """

    def do_GET(self) -> None:  # pylint:disable=invalid-name
        """Never serve the GET request."""
        time.sleep(HANG_TIME)

    def do_HEAD(self) -> None:  # pylint:disable=invalid-name
        """Never serve the HEAD request."""
        time.sleep(HANG_TIME)


HANDLERS = {
    "HEAD": SlowServerHandler,
    "GET": SlowGetServerHandler,
    "POST": SlowPostServerHandler,
    "Key": SlowPostKeyServerHandler,
    "Hang": HangingServerHandler,
}

if __name__ == "__main__":
    HOST, PORT, IMMORTAL, METHOD = "127.0.0.1", "8000", "False", "HEAD"
    if len(sys.argv) >= 2:
        HOST, PORT = sys.argv[1].split(":")

    if len(sys.argv) >= 3:
        IMMORTAL = sys.argv[2]

    if len(sys.argv) == 4:
        METHOD = sys.argv[3]

    if ast.literal_eval(IMMORTAL):
        block_signals()

    server = HTTPServer((HOST, int(PORT)), HANDLERS[METHOD])  # pylint: disable=invalid-name
    print(f"Starting slow server on {HOST}:{PORT}...")
    server.serve_forever()
