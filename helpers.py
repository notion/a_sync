"""Helper functions for the package."""


# [ Imports ]
# [ -Python ]
import asyncio
import concurrent


# [ Design ]
# * make the async thing easy/default
# * make the sync thing easy/doable


# [ Globals ]
EXECUTOR = None
EXECUTOR_THREAD_COUNT = 20


# [ Helpers ]
def get_or_create_event_loop():
    """Get or create the current event loop."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop


def get_or_create_executor():
    """Get or create an executor."""
    executor = get_executor()
    if not executor:
        executor = create_executor()
        set_executor(executor)
    return executor


def get_executor():
    """Get the executor."""
    return EXECUTOR


def set_executor(executor):
    """Get an executor to run blocking functions in."""
    global EXECUTOR
    EXECUTOR = executor


def create_executor():
    """Get an executor to run blocking functions in."""
    return concurrent.futures.ThreadPoolExecutor(EXECUTOR_THREAD_COUNT)
