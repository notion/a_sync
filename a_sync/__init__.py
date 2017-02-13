"""A module exploring some python asyncio interactions."""


# [ Imports ]
from .a_sync import (
    ExitOption,
    Parallel,
    Serial,
    ThreadExecutor,
    a_input,
    block,
    idle_event_loop,
    queue_background_thread,
    run,
    to_async,
    to_blocking,
)


# silence pyflakes
assert idle_event_loop
assert to_async
assert to_blocking
assert queue_background_thread
assert run
assert block
assert a_input
assert Parallel
assert Serial
assert ThreadExecutor
assert ExitOption
