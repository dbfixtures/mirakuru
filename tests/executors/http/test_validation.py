"""HTTP executor constructor validation tests."""

import pytest

from mirakuru import HTTPExecutor
from tests.executors.http.base import HOST, HTTP_NORMAL_CMD, PORT, XDIST_GROUP

pytestmark = pytest.mark.xdist_group(name=XDIST_GROUP)


def test_negative_request_timeout() -> None:
    """Check that a negative request timeout is rejected on construction."""
    with pytest.raises(ValueError, match="request_timeout must not be negative"):
        HTTPExecutor(HTTP_NORMAL_CMD, f"http://{HOST}:{PORT}/", request_timeout=-1)


def test_url_without_hostname() -> None:
    """Check that a url with no hostname is rejected on construction."""
    with pytest.raises(ValueError, match="does not contain hostname"):
        HTTPExecutor(HTTP_NORMAL_CMD, "http:///nohost")
