"""Small retry callable in case of specific error occurred."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from time import sleep
from typing import TypeVar

from mirakuru import ExecutorError

T = TypeVar("T")


def retry(
    func: Callable[[], T],
    timeout: int = 60,
    possible_exception: type[Exception] = ExecutorError,
) -> T:
    """Attempt to retry the function for timeout time."""
    time: datetime = datetime.now(UTC)
    timeout_diff: timedelta = timedelta(seconds=timeout)
    i = 0
    while True:
        i += 1
        try:
            res = func()
            return res
        except possible_exception as e:
            if time + timeout_diff < datetime.now(UTC):
                raise TimeoutError(f"Failed after {i} attempts") from e
            sleep(1)
