"""HTTP executor status code matching tests."""

from typing import Any

import pytest

from mirakuru import HTTPExecutor, TimeoutExpired
from tests.executors.http.base import HOST, HTTP_NORMAL_CMD, PORT, XDIST_GROUP

pytestmark = pytest.mark.xdist_group(name=XDIST_GROUP)


@pytest.mark.parametrize(
    "accepted_status, expected_timeout",
    (
        # default behaviour - only 2XX HTTP status codes are accepted
        (None, True),
        # one explicit integer status code
        (200, True),
        # one explicit status code as a string
        ("404", False),
        # status codes as a regular expression
        (r"(2|4)\d\d", False),
        # status codes as a regular expression
        ("(200|404)", False),
    ),
)
def test_http_status_codes(accepted_status: None | int | str, expected_timeout: bool) -> None:
    """Test how 'status' argument influences executor start."""
    kwargs: dict[str, Any] = {
        "command": HTTP_NORMAL_CMD,
        "url": f"http://{HOST}:{PORT}/badpath",
        "timeout": 2,
    }
    if accepted_status:
        kwargs["status"] = accepted_status
    executor = HTTPExecutor(**kwargs)

    if not expected_timeout:
        executor.start()
        executor.stop()
    else:
        with pytest.raises(TimeoutExpired):
            executor.start()
            executor.stop()
