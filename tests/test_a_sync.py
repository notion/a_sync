import functools

import asynctest
import pytest

import a_sync


def test_block():
    async def async_func():
        return 5

    def sync_func():
        return 4

    assert a_sync.block(async_func) == 5
    assert a_sync.block(sync_func) == 4


def test_block_partials():
    def sync_func_to_partial(retval):
        return retval

    async def async_func_to_partial(retval):
        return retval

    sync_partial = functools.partial(sync_func_to_partial, 5)
    async_partial = functools.partial(async_func_to_partial, 4)

    assert a_sync.block(sync_partial) == 5
    assert a_sync.block(async_partial) == 4


def test_block_works_with_CoroutineMock():
    assert 3 == a_sync.block(asynctest.CoroutineMock(return_value=3))


@pytest.mark.asyncio
async def test_run():
    async def async_func():
        return 5

    def sync_func():
        return 4

    assert await a_sync.run(async_func) == 5
    assert await a_sync.run(sync_func) == 4


@pytest.mark.asyncio
async def test_run_works_with_CoroutineMock():
    assert 3 == await a_sync.run(asynctest.CoroutineMock(return_value=3))


@pytest.mark.asyncio
async def test_run_partials():
    def sync_func_to_partial(retval):
        return retval

    async def async_func_to_partial(retval):
        return retval

    sync_partial = functools.partial(sync_func_to_partial, 5)
    async_partial = functools.partial(async_func_to_partial, 4)

    assert await a_sync.run(sync_partial) == 5
    assert await a_sync.run(async_partial) == 4
