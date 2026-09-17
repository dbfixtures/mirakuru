"""Where the HTTP test server lives, and how to talk to it."""

from http.client import OK, HTTPConnection

from tests import HTTP_SERVER_CMD

HOST = "127.0.0.1"
PORT = 7987

HTTP_NORMAL_CMD = f"{HTTP_SERVER_CMD} {PORT}"

XDIST_GROUP = f"http-port-{PORT}"
"""Every module here binds the same port, so xdist has to keep them together."""


def connect_to_server() -> None:
    """Connect to http server and assert 200 response."""
    conn = HTTPConnection(HOST, PORT)
    conn.request("GET", "/")
    assert conn.getresponse().status == OK
    conn.close()
