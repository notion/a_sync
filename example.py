"""Examples for ThreadExecutor."""


# [ Import ]
# [ -Python ]
import time
from concurrent import futures
# [ -Project ]
import a_sync


EXECUTOR = a_sync.ThreadExecutor()


def rest(seconds: int) -> int:
    """Rest function."""
    # can't use f-strings with mypy checking: https://github.com/python/mypy/issues/2265
    print("starting rest {seconds}".format(seconds=seconds))
    time.sleep(seconds)
    print("ending rest {seconds}".format(seconds=seconds))
    return seconds


# SUBMITTED_FUTURES = [EXECUTOR.submit(rest, n) for n in [1, 1, 2, 3, 5, 7, 13, 4, 6, 8, 9, 10, 11, 12]]
# _ = [EXECUTOR.submit(rest, n) for n in [1, 1, 2, 3, 5, 7, 13, 4, 6, 8, 9, 10, 11, 12]]
# submitted_futures = [executor.submit(rest, n) for n in [1, 1]]


def as_completed_example() -> None:
    """Example of using as_completed API with executor."""
    submitted_futures = [EXECUTOR.submit(rest, n) for n in [1, 1, 2, 3, 5, 7, 13, 4, 6, 8, 9, 10, 11, 12]]
    for completed_future in futures.as_completed(submitted_futures):
        print("completed: {}".format(completed_future.result()))


def individual_abandon_example() -> None:
    """Example of individual abandonment."""
    submitted_futures = [EXECUTOR.submit(rest, n) for n in [1, 1, 2, 3, 5, 7, 13, 4, 6, 8, 9, 10, 11, 12]]
    try:
        for completed_future in futures.as_completed(submitted_futures, timeout=5):
            print("completed: {}".format(completed_future.result()))
    except futures.TimeoutError:
        print("timeout occurred - abandoning remaining futures.")
        for s_future in submitted_futures:
            if not s_future.done():
                s_future.abandon()


def map_example() -> None:
    """Example of an executor map."""
    try:
        list(EXECUTOR.map(rest, [1, 1, 2, 3, 5, 7, 13, 4, 6, 8, 9, 10, 11, 12], timeout=5))
    except futures.TimeoutError:
        print("timed out")


def shutdown_wait_example() -> None:
    """Example of shutting down and waiting."""
    try:
        list(EXECUTOR.map(rest, [1, 1, 2, 3, 5, 7, 13, 4, 6, 8, 9, 10, 11, 12], timeout=5))
    except futures.TimeoutError:
        print("timed out")
        EXECUTOR.shutdown()
        print("shut down and stopped")


def shutdown_nowait_example() -> None:
    """Example of shutting down without waiting."""
    try:
        list(EXECUTOR.map(rest, [1, 1, 2, 3, 5, 7, 13, 4, 6, 8, 9, 10, 11, 12], timeout=5))
    except futures.TimeoutError:
        print("timed out")
        EXECUTOR.shutdown(wait=False)
        print("shut down and stopped")


def abandon_example() -> None:
    """Example of abandonment."""
    try:
        list(EXECUTOR.map(rest, [1, 1, 2, 3, 5, 7, 13, 4, 6, 8, 9, 10, 11, 12], timeout=5))
    except futures.TimeoutError:
        print("timed out")
        EXECUTOR.abandon()
        print("shut down and abandoned")


def context_manager_example() -> None:
    """Example of a context manager."""
    try:
        with a_sync.ThreadExecutor(on_exit=a_sync.ExitOption.WAIT) as executor:
            list(executor.map(rest, [1, 1, 2, 3, 5, 7, 13, 4, 6, 8, 9, 10, 11, 12], timeout=5))
    except futures.TimeoutError:
        print("timed out")


assert context_manager_example
assert abandon_example
assert shutdown_nowait_example
assert shutdown_wait_example
assert map_example
assert individual_abandon_example
assert as_completed_example

# as_completed_example()
# individual_abandon_example()
# map_example()
# shutdown_wait_example()
# shutdown_nowait_example()
# abandon_example()
context_manager_example()
