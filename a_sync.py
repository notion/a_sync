"""A module exploring some python asyncio interactions."""


# [ Imports ]
# [ -Python ]
import asyncio
import functools
import concurrent
# [ -Project ]
import helpers


# [ Design ]
# * make the async thing easy/default
# * make the sync thing easy/doable


# [ General ]
def to_runnable(func, *args, **kwargs):
    """Convert blocking or async func to a "runnable" - either a partial or a coroutine object."""
    # XXX return an awaitable object if one is passed in.
    if asyncio.iscoroutinefunction(func):
        async_func = func
        runnable = async_func(*args, **kwargs)
    else:
        runnable = functools.partial(func, *args, **kwargs)
    return runnable


# [ Sync API ]
def parallel(*runnables):
    """
    Return a function which will run the given args in parallel when called.

    The returned function will return a list of results in the order of the runnables given.
    Handles both awaitables and blocking functions.
    """
    # For parallelism we are using async, so everything gets converted to awaitables -
    # just use the async_parallel and then block on it.
    return helpers.to_blocking(async_parallel(*runnables))


def serial(*runnables):
    """
    Return a function which will run the given runnables in series when called.

    The returned function will return a list of results in the order of the runnables given.
    Handles both awaitables and blocking functions.
    """
    # avoid unnecessary threads - don't convert blocking functions to awaitables,
    # convert awaitables to blocking functions.
    def _serial(*runnables):
        """
        Run the given args in series.

        Return a list of results in the order of the runnables given.
        Handles both awaitables and blocking functions.
        """
        return [helpers.ensure_blocking(f)() for f in runnables]

    return to_runnable(_serial, *runnables)


def foreground(func, *args, **kwargs):
    """
    Run a function in the foreground.

    Block till the function is done, and return the results.
    Handles both async and blocking functions.
    """
    runnable = to_runnable(func, *args, **kwargs)
    blocking_func = helpers.ensure_blocking(runnable)
    return blocking_func()


def background(func, *args, **kwargs):
    """
    Run a runnable in the background.

    Returns a backgrounded_future object which you
    can use to get the results, wait, etc.
    Handles both async and blocking functions.
    """
    runnable = to_runnable(func, *args, **kwargs)
    blocking = helpers.ensure_blocking(runnable)
    # must run in an idle event loop.  if you attach it to
    # a running loop, you don't know when that loop will stop,
    # and therefore you don't know if this function will ever be
    # called, or ever complete.
    # XXX is that true?  the function is executed immediately in the executor,
    # and if the loop is idle, it gets kicked in the 'wait' functions...
    with helpers.idle_event_loop() as loop:
        # XXX need unique executor for every thread?  every time it fills up?  need to think
        # about how the tasks get queued up.
        future = loop.run_in_executor(helpers.get_or_create_executor(), blocking)
        backgrounded_future = {
            'future': future,
            'loop': loop,
            'func': func,
            'args': args,
            'kwargs': kwargs,
        }
        return backgrounded_future


def wait_for(backgrounded_future):
    """Wait for the future to error or complete."""
    loop = backgrounded_future['loop']
    future = backgrounded_future['future']
    while not future.done():
        # if the loop isn't running, you need to kick it to
        # make it check/set the future data correctly.
        if not loop.is_running():
            loop.run_until_complete(asyncio.sleep(0))
    return future.result()


def wait_for_any(*backgrounded_futures):
    """
    Wait for any of the futures to error or complete.

    Returns: completed_backgrounded_future, incomplete_backgrounded_futures
    """
    while True:
        for backgrounded_future in backgrounded_futures:
            loop = backgrounded_future['loop']
            future = backgrounded_future['future']
            # if the loop isn't running, you need to kick it to
            # make it check/set the future data correctly.
            if not loop.is_running():
                # XXX protect against thread race condition here, by ignoring the
                # loop already running error.  NEEDS TEST.
                loop.run_until_complete(asyncio.sleep(0))
            if future.done():
                backgrounded_futures = list(backgrounded_futures)
                backgrounded_futures.remove(backgrounded_future)
                return backgrounded_future, backgrounded_futures


def as_completed(*backgrounded_futures):
    """Yield the backgrounded futures as they are completed."""
    futures_left = backgrounded_futures
    while futures_left:
        completed, futures_left = wait_for_any(*futures_left)
        yield completed


def wait_for_all(*backgrounded_futures):
    """
    Wait for the futures to error or complete.

    If you only want to run things in parallel, don't use
    background and wait for all - use the parallel function, as it
    takes better advantage of async/await in a single thread.

    Will wait for all backgrounded futures to return, and will
    return a list of results in the order of the passed in args.

    The first error encountered will be raised.
    """
    return [wait_for(bf) for bf in backgrounded_futures]


# [ Async API ]
async def async_parallel(*runnables):
    """
    Run the given runnables in parallel when awaited.

    Returns a list of results in the order of the runnables given.
    Handles both awaitables and blocking functions.
    """
    awaitables = [helpers.ensure_awaitable(f) for f in runnables]
    return await asyncio.gather(*awaitables)


async def async_serial(*runnables):
    """
    Run the given runnables in series when awaited.

    Returns a list of results in the order of the runnables given.
    Handles both awaitables and blocking functions.
    """
    # use the blocking serial func to avoid creating unnecessary threads for blocking
    # runnables.  Convert it back to an awaitable because we are in an async context,
    # where you shouldn't just run an arbitrary blocking function.
    # Not only would that block this serial flow (intended), but it would block any
    # other concurrent flows in the calling event loop (unintended & probably bad).
    # This strategy produces the fewest threads (1), except when all the runnables are
    # awaitable - then it creates an unnecessary thread.  Optimize later?
    return await helpers.to_awaitable(serial(*runnables))


async def async_foreground(func, *args, **kwargs):
    """
    Run a function in the foreground.

    Awaits the function, and return the results.
    Handles both async and blocking functions.
    """
    runnable = to_runnable(func, *args, **kwargs)
    awaitable = helpers.ensure_awaitable(runnable)
    return await awaitable


async def async_background(func, *args, **kwargs):
    """
    Run a runnable in the background.

    Returns

    Schedules the runnable on the current event loop.
    Handles both async and blocking functions.
    """
    runnable = to_runnable(func, *args, **kwargs)
    awaitable = helpers.ensure_awaitable(runnable)
    future = asyncio.ensure_future(awaitable)
    backgrounded_future = {
        'future': future,
        'func': func,
        'args': args,
        'kwargs': kwargs,
    }
    return backgrounded_future


async def async_wait_for(backgrounded_future):
    """
    Wait for the future to error or complete.

    It's important to only wait for futures which were backgrounded in this loop,
    in this thread.  If you want to pass the futures around between loops and threads,
    use the sync version of this function.

    If you want this wait to actually succeed, the caller needs to make sure the loop runs
    at least until the wait_for is done.
    """
    future = backgrounded_future['future']
    return await asyncio.wait_for(future, timeout=None)


async def async_wait_for_any(*backgrounded_futures):
    """
    Wait for any of the futures to error or complete.

    Returns: completed_backgrounded_future, incomplete_backgrounded_futures
    """
    done, pending = await asyncio.wait([bf['future'] for bf in backgrounded_futures], return_when=concurrent.futures.FIRST_COMPLETED)
    first_done = done[0]
    for bf in backgrounded_futures:
        if bf['future'] == first_done:
            backgrounded_futures = list(backgrounded_futures)
            backgrounded_futures.remove(bf)
            return bf, backgrounded_futures


async def async_as_completed(*backgrounded_futures):
    """Yield the backgrounded futures as they are completed."""
    raise NotImplementedError
    # XXX not sure how to implement this - yield inside an async function
    # is an error - I want to return a generator that gets the next
    # thing as completed asynchronously...
    # futures_left = backgrounded_futures
    # while futures_left:
    #     completed, futures_left = await async_wait_for_any(*futures_left)
    #     yield completed
    # maybe with an async iterable


async def async_wait_for_all(*backgrounded_futures):
    """
    Wait for the futures to error or complete.

    If you only want to run things in parallel, don't use
    background and wait for all - use the parallel function, as it
    takes better advantage of async/await in a single thread.

    Will wait for all backgrounded futures to return, and will
    return a list of results in the order of the passed in args.

    The first error encountered will be raised.
    """
    results = []
    for bf in backgrounded_futures:
        results.append(await async_wait_for(bf))
    return results
