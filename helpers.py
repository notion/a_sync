"""Helper functions for the package."""


# [ Imports ]
# [ -Python ]
import asyncio
from concurrent import futures
from typing import Optional


# [ Globals ]
EXECUTOR = None
EXECUTOR_THREAD_COUNT = 20


# [ Helpers ]
def get_or_create_event_loop() -> asyncio.AbstractEventLoop:
    """Get or create the current event loop."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop


def get_or_create_executor() -> futures.ThreadPoolExecutor:
    """Get or create an executor."""
    executor = get_executor()
    if not executor:
        executor = create_executor()
        set_executor(executor)
    return executor


def get_executor() -> Optional[futures.ThreadPoolExecutor]:
    """Get the executor."""
    return EXECUTOR


def set_executor(executor: futures.ThreadPoolExecutor) -> None:
    """Get an executor to run blocking functions in."""
    global EXECUTOR
    EXECUTOR = executor


def create_executor() -> futures.ThreadPoolExecutor:
    """Get an executor to run blocking functions in."""
    return futures.ThreadPoolExecutor(EXECUTOR_THREAD_COUNT)
