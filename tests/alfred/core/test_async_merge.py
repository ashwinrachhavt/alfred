import asyncio

import pytest

from alfred.core.async_merge import merge_async_generators


async def _gen_items(items: list[tuple[float, str]]):
    for delay, value in items:
        await asyncio.sleep(delay)
        yield value


@pytest.mark.asyncio
async def test_merge_single_generator():
    gen = _gen_items([(0, "a"), (0, "b"), (0, "c")])
    results = [item async for item in merge_async_generators(gen)]
    assert results == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_merge_two_generators_interleaved():
    fast = _gen_items([(0.01, "fast1"), (0.01, "fast2"), (0.01, "fast3")])
    slow = _gen_items([(0.05, "slow1")])
    results = [item async for item in merge_async_generators(fast, slow)]
    assert results.index("fast1") < results.index("slow1")
    assert len(results) == 4


@pytest.mark.asyncio
async def test_merge_empty_generators():
    async def empty():
        return
        yield

    results = [item async for item in merge_async_generators(empty(), empty())]
    assert results == []


@pytest.mark.asyncio
async def test_merge_one_empty_one_full():
    async def empty():
        return
        yield

    full = _gen_items([(0, "a"), (0, "b")])
    results = [item async for item in merge_async_generators(empty(), full)]
    assert results == ["a", "b"]


@pytest.mark.asyncio
async def test_merge_generator_exception_propagates():
    async def failing():
        yield "ok"
        raise ValueError("boom")

    gen = _gen_items([(0, "a")])
    with pytest.raises(ValueError, match="boom"):
        _ = [item async for item in merge_async_generators(failing(), gen)]
