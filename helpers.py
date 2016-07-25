"""Helper functions for the package."""


# [ Imports ]
# [ -Python ]
import asyncio
import inspect
import contextlib
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


@contextlib.contextmanager
def idle_event_loop():
    """
    An idle event loop context manager.

    Leaves the current event loop in place if it's not running.
    Creates and sets a new event loop as the default if the current default IS running.
    Restores the original event loop on exit.
    """
    original_loop = get_or_create_event_loop()
    try:
        if original_loop.is_running():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        else:
            loop = original_loop
        yield loop
    finally:
        asyncio.set_event_loop(original_loop)


async def to_awaitable(func):
    """Turn a blocking function into an awaitable."""
    # getting existing ok because we're not in a loop
    # (need error handling in case we are?)
    # might need to create because we might not be in the main thread.
    # don't want to use a unique loop here because this runs in the caller's
    # context, which we're not passing the loop back into.
    # (creating the loop sets it in the global context... it would be
    # better to make that explicit somehow)
    loop = get_or_create_event_loop()
    # create a loop inside the executor?
    # allows everyone to use default loop
    # adds unnecessary overhead for functions which don't need one...
    # the common case will be that we don't need a loop, so let's not do that here.
    # means anyone who wants to use a loop will have to get_or_create first.
    # Run in executor returns a future, which is bound to the given loop.
    # Don't return the future - you can't control the context it runs
    # in if you do, and that might be a different event loop or thread,
    # which will cause an error.  Await it here and return its results instead.
    return await loop.run_in_executor(get_or_create_executor(), func)


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


def set_executor_thread_count(count):
    """Set the executor thread count."""
    global EXECUTOR_THREAD_COUNT
    EXECUTOR_THREAD_COUNT = count


def to_blocking(awaitable):
    """Turn an awaitable function into a blocking function."""
    def blocking():
        """A blocking wrapper around an awaitable."""
        # create and use a unique loop - we don't care if we're in a loop
        # already or not, we just want to run the awaitable to completion.
        # Doing so with the default loop is fine if nothing is running, but
        # if it's already running we get an error.  Create and use a new event
        # loop in that case.
        # The expectation is that the awaitable is a coroutine object, not a future.
        # XXX need defensive code here for ^.  Futures might be bound to a specific loop,
        # which is fine if that loop is not running, and we can get to it and use it,
        # but we're neither checking for that or doing that (pulling that loop out and using it).
        # XXX need defensive code here in case the arg is not awaitable.
        with idle_event_loop() as loop:
            return loop.run_until_complete(awaitable)
    return blocking


def ensure_awaitable(func_or_awaitable):
    """Return an awaitable, creating one if a blocking function is passed in."""
    if inspect.isawaitable(func_or_awaitable):
        awaitable = func_or_awaitable
    else:
        func = func_or_awaitable
        awaitable = to_awaitable(func)
    return awaitable


def ensure_blocking(func_or_awaitable):
    """Return a blocking function, creating one if an awaitable is passed in."""
    if inspect.isawaitable(func_or_awaitable):
        awaitable = func_or_awaitable
        func = to_blocking(awaitable)
    else:
        func = func_or_awaitable
    return func
