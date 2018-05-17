import a_sync
import asynctest

import pytest


def test_block():
    async def async_func():
        return 5

    def sync_func():
        return 4

    assert a_sync.block(async_func) == 5
    assert a_sync.block(sync_func) == 4


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
