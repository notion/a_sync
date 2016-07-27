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


class RunnableScheduler:
    """Schedule function calls."""

    def __init__(self):
        """Init state."""
        self._runnables = []

    def schedule(self, runnable, *args, **kwargs):
        """
        Schedule a runnable to be run.

        By common sense, if not by definition, if you are scheduling something to run,
        it has not run yet.  coro objects and futures of any kind don't fit that description.

        Defend against those as arguments - only accept blocking and async functions.
        """
        if not hasattr(runnable, '__call__'):
            raise TypeError("{} is not callable.  Try just waiting for it instead of running it?".format(
                runnable
            ))
        self._runnables.append([runnable, args, kwargs])
        return self

    def get(self):
        """Get the list of runnables."""
        return self._runnables


class Parallel:
    """
    Parallel runner.

    Challenges:
        * running things in parallel
        * thinking about async def vs def - you can pass either in.
        * thinking about ^ vs coro obj vs async future vs concurrent future - accepts all.
        * is it async vs blocking - if called from an async context, is it going to play
          nicely (yield back & be concurrent)? (run async vs block) (new loop or current loop)
    """

    def __init__(self):
        """Init state."""
        self._scheduler = RunnableScheduler()

    def schedule(self, runnable, *args, **kwargs):
        """Schedule a runnable to be run."""
        self._scheduler.schedule(runnable, *args, **kwargs)
        return self

    def _get_runnables(self):
        """Get the scheduled runnables."""
        return self._scheduler.get()

    async def run(self):
        """
        Run the scheduled runnables in the thread loop.

        According to https://docs.python.org/3/library/asyncio-eventloops.html#event-loop-policies-and-the-default-policy,
        python manages a global loop per thread.  As long as nobody creates and uses secondary
        loops in the thread, everyone should be able to depend on the global loop being the
        one that's calling this function.

        It's important then, that anyone running a new loop does so in a new thread.
        XXX this discussion belongs somewhere else.
        """
        # split the runnables
        async_runnables = [r for r in self._get_runnables() if asyncio.iscoroutinefunction(r[0])]
        sync_runnables = [r for r in self._get_runnables() if not asyncio.iscoroutinefunction(r[0])]
        # convert sync to async
        async_runnables += [(to_async(r[0]), r[1], r[2]) for r in sync_runnables]
        # create tasks
        loop = asyncio.get_event_loop()
        tasks = [loop.create_task(r(*args, **kwargs)) for r, args, kwargs in async_runnables]
        gathered = asyncio.gather(*tasks)
        # await them
        return await asyncio.wait_for(gathered, timeout=None)

    def block(self):
        """Run the scheduled runnables in an idle loop."""
        with helpers.idle_event_loop() as loop:
            return loop.run_until_complete(self.run())


class Serial:
    """
    Serial runner.

    Challenges:
        * running things in series
        * thinking about async def vs def - you can pass either in.
        * thinking about ^ vs coro obj vs async future vs concurrent future - accepts all.
        * is it async vs blocking - if called from an async context, is it going to play
          nicely (yield back & be concurrent)? (run async vs block) (new loop or current loop)
    """

    def __init__(self):
        """Init state."""
        self._scheduler = RunnableScheduler()

    def schedule(self, runnable, *args, **kwargs):
        """Schedule a runnable to be run."""
        self._scheduler.schedule(runnable, *args, **kwargs)
        return self

    def _get_runnables(self):
        """Get the scheduled runnables."""
        return self._scheduler.get()

    async def run(self):
        """Run the scheduled runnables in the thread's loop."""
        results = []
        for r, args, kwargs in self._get_runnables():
            if not asyncio.iscoroutinefunction(r):
                r = to_async(r)
            results.append(await r(*args, **kwargs))
        return results

    def block(self):
        """Run the scheduled runnables in an idle loop."""
        results = []
        for r, args, kwargs in self._get_runnables():
            if asyncio.iscoroutinefunction(r):
                r = to_blocking(r)
            results.append(r(*args, **kwargs))
        return results


def to_async(blocking):
    """Convert a blocking function to an async function."""
    async def wrapped_blocking(*args, **kwargs):
        """Wrapper for a blocking function."""
        partial = functools.partial(blocking, *args, **kwargs)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(helpers.get_or_create_executor(), partial)
    return wrapped_blocking


def to_blocking(async_func):
    """Convert an async function to a blocking function."""
    def wrapped_async(*args, **kwargs):
        """Wrapper for an async function."""
        with helpers.idle_event_loop() as loop:
            return loop.run_until_complete(async_func(*args, **kwargs))
    return wrapped_async


async def run(runnable, *args, **kwargs):
    """Run a function, whether async or sync."""
    return await Serial().schedule(runnable, *args, **kwargs).run()


def block(runnable, *args, **kwargs):
    """Run a function, whether async or sync."""
    return Serial().schedule(runnable, *args, **kwargs).block()
