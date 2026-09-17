"""HTTP executor tests for the request target the status check sends."""

import sys

import pytest

from mirakuru import HTTPExecutor, TimeoutExpired
from tests import TEST_SERVER_PATH
from tests.executors.http.base import HOST, PORT, XDIST_GROUP
from tests.server_for_tests import REQUEST_TARGET, REQUEST_URL_PART

pytestmark = pytest.mark.xdist_group(name=XDIST_GROUP)

HTTP_TARGET_CMD = f"{sys.executable} {TEST_SERVER_PATH} {HOST}:{PORT} False Target"


@pytest.mark.parametrize("target_id", (1, 2))
@pytest.mark.parametrize("url_suffix", ("", "#fragment"))
def test_query_and_params_are_sent(target_id: int, url_suffix: str) -> None:
    """Check that the whole request target, fragment aside, reaches the server."""
    cmd = f"{HTTP_TARGET_CMD}{target_id}"
    with HTTPExecutor(
        cmd,
        f"http://{HOST}:{PORT}{REQUEST_URL_PART[target_id]}{url_suffix}",
        timeout=30,
    ) as executor:
        assert executor.running() is True


@pytest.mark.parametrize("target_id", (1, 2))
def test_path_only_target_times_out(target_id: int) -> None:
    """Check that the server this is measured against does discriminate.

    Without the query string and the ``;params`` it answers 500, so a passing
    `test_query_and_params_are_sent` cannot be a server that says 200 to anything.
    """
    path = REQUEST_TARGET[target_id].split(";")[0].split("?")[0]
    cmd = f"{HTTP_TARGET_CMD}{target_id}"
    executor = HTTPExecutor(cmd, f"http://{HOST}:{PORT}{path}", timeout=2)

    with pytest.raises(TimeoutExpired):
        executor.start()

    assert executor.running() is False
