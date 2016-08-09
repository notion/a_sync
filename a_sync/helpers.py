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
    """
    Get or create the current event loop.

    Gets the current event loop if it exists, else creates, sets as global,
    and then returns an asyncio event loop.

    Args:
        None

    Returns:
        event_loop - an asyncio event loop
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop


def get_or_create_executor() -> futures.ThreadPoolExecutor:
    """
    Get or create an executor.

    Gets the current executor if one exists, else creates, sets as global,
    and then returns a futures.ThreadPoolExecutor.

    Args:
        None

    Returns:
        executor - a futures.ThreadPoolExecutor
    """
    executor = get_executor()
    if not executor:
        executor = create_executor()
        set_executor(executor)
    return executor


def get_executor() -> Optional[futures.ThreadPoolExecutor]:
    """
    Get the executor.

    Returns the current global executor - either a futures.ThreadPoolExecutor or None, if none has been set.

    Args:
        None

    Returns:
        executor - a futures.ThreadPoolExecutor or None
    """
    return EXECUTOR


def set_executor(executor: futures.ThreadPoolExecutor) -> None:
    """
    Set an executor to run blocking functions in.

    Args:
        executor - a futures.ThreadPoolExecutor to set as global default.

    Returns:
        None
    """
    global EXECUTOR
    EXECUTOR = executor


def create_executor() -> futures.ThreadPoolExecutor:
    """
    Create an executor to run blocking functions in.

    Args:
        None

    Returns:
        executor - a futures.ThreadPoolExecutor.
    """
    return futures.ThreadPoolExecutor(EXECUTOR_THREAD_COUNT)
