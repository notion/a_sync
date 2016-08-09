# a_sync
An async helper library for Python's async functionality.

# Under construction
The repo is "under construction" - it serves at the moment as a place to put the project and "get it out there", but there are a lot of project-management tasks to do, including getting a sensible README up.

# Alpha status
The repo is definitely "alpha".  Possibly "pre-alpha", if that's a thing.  At the moment it's got one internal user for code that isn't even published internally yet.

Basically anything is subject to change.  This includes any of the API, the project name, and even the project's existence.  It was initially created to help me understand how Python's async stuff worked, and has grown as I've decided that the asyncio lib is lower-level than I want to deal with, and as I explored different "well now how do I do this?" questions.

Feedback, new issues, suggestions, criticisms, etc are welcomed and encouraged.  If the project turns out to be truly worth it, I'll be happy to have shared it.  If not, I'll be happy to have learned why it's not, and how to do async in python better.

# Thoughts
The below are some thoughts about using the async support in python - they're a little stream-of-consciousness, and
only very lightly edited.

Python runs in a sync context - need to support async calls in the sync context, which means supporting
subcomponents using the event loop.  Or some other loop.  Or some other async runner (like the curio kernel).  Code
should not make any assumptions about the context it's running in.

You can await any number of levels down, but if you want to add something to the current event loop...you'll get an
async future back, which requires knowledge of the loop it was created for to be running in order to use properly. 
Unfortunately, asyncio doesn't yet allow you to figure that out, so you have to be careful about passing those futures 
around.  It seems to me that asyncio futures should only be used at the same level as the asyncio event loop is used.
There is an unfortunate implicit dependency there which is further complicated by the asynchronous nature of the
library and is even harder to reason about in the face of mutliple threads... I would recommend that any use of asyncio
futures be tightly controlled.

Levels of concurrency:
* When to be serial - when you want to do a single operation and don't want anything else to happen till it's done.
* When to be concurrent in a single thread - when you have things you want done concurrently, but none of them are
blocking.
* When to be concurrent in multiple threads - when you have blocking operations.
* When to be multi-process - when your cpu fills up.
* When to be multi-host - when all your cpu's fill up.

So...you want single-threaded-blocking if you want just one thing done at the top level, logical concurrency any
other time, thread-concurrency when you have truly blocking operations, and actual temporal concurrency when you've run out
of computation power in your processor, or when you can actually break things into independent tasks such that actually
running in parallel actually gets you a speed boost that you care about..  (this can be expanded to other hosts, not
just other cpu's, though you want minimal communication the further apart your parts are (single-threaded-blocking ->
single-threaded concurrent -> multi-threaded concurrent -> multiprocess-concurrent -> multi-host concurrent))

The only dependable "top-level" is the `__main__` script area.  Any function calls you define and call in the main
script can be called from within other functions and from other modules, and you can't ever know if they're being run
concurrently or not.  Even the main script is often refactored out into a function call, which can then be used
anywhere.

From that, I'd reason that you always want to be concurrent.  The major advantage of `await` is that you get to pick
where your thread's control moves off to run other things, which allows you to explicitly run areas of code 'atomically'
in your thread without dealing with locks/semaphores/events.  From that, I'd reason that most of the time you want to
use the await-style concurrency instead of thread-level concurrency.

So forget the synchronous context.  Write everything new asynchronously.  Wrap all the blocking calls.

Stretch goals:
* find a way to simulate the await 'atomic' guarantees in threads, because threads are always going to be necessary
for dealing with blocking calls.
* find a way to grow your executor thread pool when you need more blocking concurrency and there's CPU available.
* find a way to grow and load balance into threads on other processors.
* find a way to grow and load balance into processors on other hosts.

Further musings given the stretch goals - this assumes you want python for other reasons than concurrency.  there are 
other languages which are explicitly designed for concurrency from the start, and usually features designed into the
lanugage are easier to work with than libraries built on top are.


# API

## Functions
### `idle_event_loop() -> Generator`

An idle event loop context manager.

Leaves the current event loop in place if it's not running.
Creates and sets a new event loop as the default if the current default IS running.
Restores the original event loop on exit.

**Args:**
* None

**Returns:**
* idle_event_loop_manager - a context manager which yields an idle event loop
    for you to run async functions in.


### `to_async(blocking_func: AnyCallable) -> AnyCallable`
    
Convert a blocking function to an async function.

If the argument is already a coroutine function, it is returned unchanged.

If the argument is a partial which wraps a coroutine function, it is returned
unchanged.

The blocking function is made into an awaitable by wrapping its call inside
an awaitable function.

On the assumption that a blocking function is long-running, and that an
async caller wants to run other things concurrently, the blocking function
is called from the running loop's thread/process executor, which means
it runs in a thread.  This allows concurrent running, but introduces possible
thread-safety issues, which the caller should be aware of.

**Args:**
* blocking_func - a blocking function

**Returns:**
* async_func - an awaitable function


### `to_blocking(async_func: AnyCallable) -> AnyCallable`

Convert an async function to a blocking function.

If the argument is already a blocking function, it is returned unchanged.

If the argument is a partial for an awaitable, it is converted.

The awaitable function is made blocking by wrapping its call in a blocking
function, which gets/creates an idle asyncio event loop and runs the
awaitable in it until it is complete.

**Args:**
* async_func - an async function

**Returns:**
* blocking_func - a blocking function



### `async queue_background_thread` *not provided*

No async background task here because that depends on knowing the environment
of the caller, as far as async context goes, and you can't.  For example,
if the caller is being executed via the curio kernel, and we add a task to the
current asyncio event loop, that task will never complete.


### `queue_background_thread(func: Callable, *args, **kwargs) -> futures.Future`
    
Queue the function to be run in a thread, but don't wait for it.

If the thread pool executor is processing on all threads, it will queue this
task.  There's currently no way to check it or expand it's pool, hence the
name of the function and the summary have been updated to reflect that..

**Args:**
* func - the function to run
* `*args` - the args to call the function with
* `**kwargs` - the kwargs to call the function with

**Returns:**
* future - a concurrent.futures Future for the function.



### `async run(func: AnyCallable, *args, **kwargs) -> Any`
Run a function in an async manner, whether the function is async or blocking.

**Args:**
* func - the function (async or blocking) to run
* `*args` - the args to run the function with
* `**kwargs` - the kwargs to run the function with

**Returns:**
* coro - a coroutine object to await

**Coro Returns:**
* result - whatever the function returns when it's done.


### `block(func: AnyCallable, *args, **kwargs) -> Any`

Run a function in a blocking manner, whether the function is async or blocking.

Args:
* func - the function (async or blocking) to run
* `*args` - the args to run the function with
* `**kwargs` - the kwargs to run the function with

**Returns:**
* result - whatever the function returns when it's done.


## Parallel Class
### `class Parallel`

Parallel runner.

Provides a way to:
    * schedule a heterogeneous mix of blocking and awaitable functions
    * run those functions all in parallel
    * to run them in either a blocking or an asynchronous manner
    * to receive the results in the order in which the functions were passed in.
    * to run them as many times as desired (similarly to a partial function)

It's analogous to a partial function, but instead of supplying args for a function and getting
a function back, you supply args for as many functions as you like, and get an function back with which
you can run those functions and arguments in parallel, either synchronously or asynchronously.

**Args:**
* None


### `schedule(self, func, *args, **kwargs) -> 'Parallel'`
Schedule a function to be run.

**Args:**
* func - the function to schedule
* `*args` - the args to call the function with
* `**kwargs` - the kwargs to call the function with

**Returns:**
* parallel - the parallel object, to allow chaining.


### `async run(self) -> List[Any]`
Run the scheduled functions in parallel, asynchronously.

**Args:**
* None

**Returns:**
* list - a list of the results from the scheduled functions, in the
    order they were scheduled in.

Note that while this function is awaitable, the scheduled functions are
run in an asyncio loop in a separate thread.  We cannot create asyncio
tasks and run them in the current thread because that depends on knowing the environment
of the caller, as far as async context goes, and you can't.  For example,
if the caller is being executed via the curio kernel, and we add a task to the
current asyncio event loop, that task will never complete.

Our only alternative is to run in an independent loop that we control.  The
only way to actually make that concurrent instead of blocking in this function
is to run that loop in its own thread.


### `block(self) -> List[Any]`
Run the scheduled functions in parallel, blocking.

**Args:**
* None

**Returns:**
* list - a list of the results from the scheduled functions, in the
    order they were scheduled in.


## Serial Class
### `class Serial`
Serial runner.

Provides a way to:
    * schedule a heterogeneous mix of blocking and awaitable functions
    * run those functions all in series
    * to run them in either a blocking or an asynchronous manner
    * to receive the results in the order in which the functions were passed in.
    * to run them as many times as desired (similarly to a partial function)

It's analogous to a partial function, but instead of supplying args for a function and getting
a function back, you supply args for as many functions as you like, and get an function back with which
you can run those functions and arguments in series, either synchronously or asynchronously.

**Args:**
* None


### `schedule(self, func: Callable, *args, **kwargs) -> 'Serial'`

Schedule a function to be run.

**Args:**
* func - the function to schedule
* `*args` - the args to call the function with
* `**kwargs` - the kwargs to call the function with

**Returns:**
* series - the series object, to allow chaining.


### `async run(self) -> List[Any]`

Run the scheduled functions in series, asynchronously.

**Args:**
    None

**Returns:**
* list - a list of the results from the scheduled functions, in the
    order they were scheduled in.


### `block(self) -> List[Any]`

Run the scheduled functions in series, blocking.

**Args:**
* None

**Returns:**
* list - a list of the results from the scheduled functions, in the
    order they were scheduled in.
