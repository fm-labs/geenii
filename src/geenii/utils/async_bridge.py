"""
Run coroutines from synchronous code on a single long-lived background event loop.

Async-only libraries (e.g. the fastmcp client) bind their connections to the loop they were
opened on. Running every coroutine on the same background loop keeps such clients usable
across calls, no matter which thread the sync caller runs on.
"""

from __future__ import annotations

import asyncio
import atexit
import logging
import threading
from typing import Any, Coroutine, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

_loop: asyncio.AbstractEventLoop | None = None
_thread: threading.Thread | None = None
_lock = threading.Lock()


def _run_loop(loop: asyncio.AbstractEventLoop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


def get_loop() -> asyncio.AbstractEventLoop:
    """Return the background event loop, starting it on first use."""
    global _loop, _thread
    with _lock:
        if (
            _loop is None
            or _loop.is_closed()
            or _thread is None
            or not _thread.is_alive()
        ):
            loop = asyncio.new_event_loop()
            thread = threading.Thread(
                target=_run_loop, args=(loop,), name="geenii-async-bridge", daemon=True
            )
            thread.start()
            _loop, _thread = loop, thread
            logger.debug("Started async bridge event loop")
        return _loop


def run_sync(coro: Coroutine[Any, Any, T], timeout: float | None = None) -> T:
    """
    Run a coroutine on the background loop and block until it returns.

    Must not be called from the background loop itself (that would deadlock).
    """
    loop = get_loop()
    if threading.current_thread() is _thread:
        coro.close()
        raise RuntimeError(
            "run_sync() called from the async bridge loop; await the coroutine instead"
        )

    future = asyncio.run_coroutine_threadsafe(coro, loop)
    try:
        return future.result(timeout)
    except BaseException:
        # timeout, KeyboardInterrupt, ...: don't leave the coroutine running in the background
        future.cancel()
        raise


def shutdown(timeout: float = 5.0):
    """Cancel pending tasks and stop the background loop."""
    global _loop, _thread
    with _lock:
        loop, thread = _loop, _thread
        _loop, _thread = None, None
    if loop is None or loop.is_closed() or thread is None or not thread.is_alive():
        return

    async def _cancel_pending():
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    try:
        asyncio.run_coroutine_threadsafe(_cancel_pending(), loop).result(timeout)
    except Exception as e:
        logger.warning(f"Error cancelling async bridge tasks: {e}")
    loop.call_soon_threadsafe(loop.stop)
    thread.join(timeout)
    if not thread.is_alive():
        loop.close()


atexit.register(shutdown)
