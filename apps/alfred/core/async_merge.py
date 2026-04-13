"""Merge multiple async generators into a single stream."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator


async def merge_async_generators(*gens: AsyncGenerator) -> AsyncGenerator:
    """Merge N async generators, yielding from whichever produces a value first.

    If any generator raises an exception, it propagates immediately and
    remaining generators are cancelled.
    """
    queue: asyncio.Queue[tuple[bool, object]] = asyncio.Queue()

    async def _feed(gen: AsyncGenerator) -> None:
        try:
            async for item in gen:
                await queue.put((False, item))
        except Exception as exc:
            await queue.put((False, exc))
            raise
        finally:
            await queue.put((True, None))

    tasks = [asyncio.create_task(_feed(g)) for g in gens]
    done_count = 0
    try:
        while done_count < len(gens):
            is_sentinel, value = await queue.get()
            if is_sentinel:
                done_count += 1
            elif isinstance(value, Exception):
                raise value
            else:
                yield value
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
