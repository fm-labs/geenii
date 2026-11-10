import asyncio
import sys
import textwrap
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from geenii.mcp_client import McpClient
from geenii.tool.common import ToolCallContext
from geenii.tool.python import PythonFunctionTool
from geenii.utils import async_bridge
from geenii.utils.async_bridge import run_sync


def test_run_sync_returns_result():
    async def add(a, b):
        await asyncio.sleep(0)
        return a + b

    assert run_sync(add(1, 2)) == 3


def test_run_sync_propagates_exceptions():
    async def fail():
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        run_sync(fail())


def test_run_sync_uses_one_loop_across_threads():
    async def current_loop():
        return asyncio.get_running_loop()

    with ThreadPoolExecutor(max_workers=4) as pool:
        loops = set(pool.map(lambda _: run_sync(current_loop()), range(8)))
    assert loops == {async_bridge.get_loop()}


def test_run_sync_timeout_cancels_coroutine():
    cancelled = threading.Event()

    async def slow():
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    with pytest.raises(TimeoutError):
        run_sync(slow(), timeout=0.05)
    assert cancelled.wait(1)


def test_run_sync_from_bridge_loop_raises():
    async def nested():
        coro = asyncio.sleep(0)
        run_sync(coro)

    with pytest.raises(RuntimeError, match="async bridge loop"):
        run_sync(nested())


def test_python_function_tool_supports_sync_and_async_handlers():
    async def async_greet(name: str):
        await asyncio.sleep(0)
        return f"hello {name}"

    sync_tool = PythonFunctionTool(name="sync_greet", handler=lambda name: f"hi {name}")
    async_tool = PythonFunctionTool(name="async_greet", handler=async_greet)

    assert sync_tool.invoke(args={"name": "a"}, ctx=ToolCallContext(cwd=".")).text == "hi a"
    assert async_tool.invoke(args={"name": "b"}, ctx=ToolCallContext(cwd=".")).text == "hello b"


MCP_SERVER = textwrap.dedent("""
    from fastmcp import FastMCP

    mcp = FastMCP("test")

    @mcp.tool
    def add(a: int, b: int) -> int:
        return a + b

    if __name__ == "__main__":
        mcp.run(show_banner=False)
""")


@pytest.fixture
def mcp_client(tmp_path):
    script = tmp_path / "server.py"
    script.write_text(MCP_SERVER)
    client = McpClient("test", {"type": "stdio", "command": sys.executable, "args": [str(script)]})
    yield client
    client.close()


def test_mcp_client_reuses_connection_across_threads(mcp_client):
    tools = mcp_client.list_tools()
    assert [t["name"] for t in tools] == ["add"]

    # the persistent connection opened above is reused from other threads
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda i: mcp_client.call_tool("add", {"a": i, "b": 1}), range(3)))
    assert [r.structured_content["result"] for r in results] == [1, 2, 3]
