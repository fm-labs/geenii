import asyncio
import json
import threading
import time

import pytest
from fastapi.testclient import TestClient

from geenii import mcp_loader
from geenii.mcp_loader import McpToolLoader
from geenii.server import server as server_mod
from geenii.server.server import app
from geenii.tool.registry import ToolRegistry
from geenii.utils.cached import SqliteCacheStore

TOOLS = {
    "alpha": [{"name": "a1"}, {"name": "a2"}],
    "beta": [{"name": "b1"}],
}


class FakeDiscover:
    """Stands in for read_mcp_server_tools. Servers listed in `gates` block until their event is set."""

    def __init__(self, tools=None):
        self.tools = dict(TOOLS if tools is None else tools)
        self.calls: list[str] = []
        self.gates: dict[str, threading.Event] = {}
        self.fail: set[str] = set()
        self.invalidated: list[str] = []
        self._lock = threading.Lock()

    def __call__(self, name):
        with self._lock:
            self.calls.append(name)
        gate = self.gates.get(name)
        if gate is not None:
            assert gate.wait(5)
        if name in self.fail:
            raise RuntimeError(f"{name} is down")
        return self.tools[name]

    def invalidate(self, name):
        self.invalidated.append(name)


@pytest.fixture
def mcp_file(mcp_dirs):
    root, _ = mcp_dirs
    root.parent.mkdir(parents=True)
    root.write_text(json.dumps({"mcpServers": {"alpha": {"command": "a"}, "beta": {"command": "b"}}}))
    return root


@pytest.fixture
def discover():
    return FakeDiscover()


@pytest.fixture
def loader(mcp_file, discover, monkeypatch):
    """A fresh process-wide loader using the fake discovery."""
    instance = McpToolLoader(discover=discover, max_workers=4, retry_cooldown=0)
    monkeypatch.setattr(mcp_loader, "_loader", instance)
    yield instance
    instance.shutdown()


def wait_for(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def state(loader, name):
    return loader.status(name)[0]["state"]


# ---------- loader ----------


def test_one_discovery_per_server(loader, discover):
    discover.gates["alpha"] = threading.Event()
    first = loader.ensure("alpha")
    second = loader.ensure("alpha")
    assert first is second
    discover.gates["alpha"].set()
    assert first.result(5) == TOOLS["alpha"]
    assert loader.ensure("alpha") is first
    assert discover.calls == ["alpha"]


def test_attached_registry_gets_tools_as_servers_finish(loader, discover):
    discover.gates["beta"] = threading.Event()
    registry = ToolRegistry()
    loader.attach(registry)
    loader.start()

    assert wait_for(lambda: state(loader, "alpha") == "ready")
    assert registry.list_tool_names() == {"mcp__alpha__a1", "mcp__alpha__a2"}
    assert state(loader, "beta") == "loading"

    discover.gates["beta"].set()
    assert wait_for(lambda: state(loader, "beta") == "ready")
    assert "mcp__beta__b1" in registry
    assert loader.status("beta")[0]["tool_count"] == 1


def test_attach_after_load_registers_finished_servers(loader):
    loader.ensure("alpha").result(5)
    registry = ToolRegistry()
    loader.attach(registry)
    assert registry.list_tool_names() == {"mcp__alpha__a1", "mcp__alpha__a2"}


def test_failed_server_is_retried(loader, discover):
    discover.fail.add("alpha")
    with pytest.raises(RuntimeError):
        loader.ensure("alpha").result(5)
    assert wait_for(lambda: state(loader, "alpha") == "failed")
    assert loader.status("alpha")[0]["error"] == "alpha is down"

    discover.fail.clear()
    assert loader.ensure("alpha").result(5) == TOOLS["alpha"]
    assert wait_for(lambda: state(loader, "alpha") == "ready")
    assert loader.status("alpha")[0]["attempts"] == 2


def test_failed_server_is_not_retried_within_cooldown(mcp_file, discover):
    loader = McpToolLoader(discover=discover, retry_cooldown=3600)
    try:
        discover.fail.add("alpha")
        failed = loader.ensure("alpha")
        with pytest.raises(RuntimeError):
            failed.result(5)
        assert loader.ensure("alpha") is failed
        assert discover.calls == ["alpha"]
    finally:
        loader.shutdown()


def test_register_into_skips_servers_still_loading(loader, discover):
    discover.gates["beta"] = threading.Event()
    registry = ToolRegistry()
    loader.register_into(registry, {"alpha", "beta", "unknown"}, timeout=0.2)
    assert registry.list_tool_names() == {"mcp__alpha__a1", "mcp__alpha__a2"}
    discover.gates["beta"].set()


def test_register_into_skips_failed_servers(loader, discover):
    discover.fail.add("beta")
    registry = ToolRegistry()
    loader.register_into(registry)
    assert registry.list_tool_names() == {"mcp__alpha__a1", "mcp__alpha__a2"}


def test_reload_replaces_tools(loader, discover):
    registry = ToolRegistry()
    loader.attach(registry)
    loader.ensure("alpha").result(5)

    discover.tools["alpha"] = [{"name": "new"}]
    loader.reload("alpha").result(5)
    assert wait_for(lambda: registry.list_tool_names() == {"mcp__alpha__new"})
    assert discover.invalidated == ["alpha"]
    assert discover.calls == ["alpha", "alpha"]


def test_superseded_discovery_is_ignored(loader, discover):
    registry = ToolRegistry()
    loader.attach(registry)
    gate = threading.Event()
    discover.gates["alpha"] = gate
    stale = loader.ensure("alpha")
    assert wait_for(lambda: discover.calls == ["alpha"])

    del discover.gates["alpha"]
    discover.tools["alpha"] = [{"name": "new"}]
    loader.reload("alpha").result(5)
    assert wait_for(lambda: registry.list_tool_names() == {"mcp__alpha__new"})

    # the first discovery finishes last; its result must not replace the reloaded tools
    discover.tools["alpha"] = [{"name": "old"}]
    gate.set()
    assert stale.result(5) == [{"name": "old"}]
    time.sleep(0.05)
    assert registry.list_tool_names() == {"mcp__alpha__new"}
    assert state(loader, "alpha") == "ready"


def test_forget_removes_tools(loader):
    registry = ToolRegistry()
    loader.attach(registry)
    loader.start()
    assert wait_for(lambda: len(registry) == 3)
    loader.forget("alpha")
    assert registry.list_tool_names() == {"mcp__beta__b1"}


def test_status_lists_unloaded_servers(loader):
    assert [(s["name"], s["state"]) for s in loader.status()] == [("alpha", "pending"), ("beta", "pending")]


def test_requested_server_is_queued_until_a_worker_is_free(mcp_file, discover):
    loader = McpToolLoader(discover=discover, max_workers=1)
    try:
        discover.gates["alpha"] = threading.Event()
        loader.start()
        assert wait_for(lambda: state(loader, "alpha") == "loading")
        assert state(loader, "beta") == "queued"
        discover.gates["alpha"].set()
        assert wait_for(lambda: state(loader, "beta") == "ready")
    finally:
        loader.shutdown()


def test_shutdown_rejects_new_work(mcp_file, discover):
    loader = McpToolLoader(discover=discover)
    loader.shutdown()
    with pytest.raises(RuntimeError):
        loader.ensure("alpha")


# ---------- server startup ----------


def test_tool_registry_init_does_not_wait_for_mcp_servers(loader, discover):
    discover.gates["alpha"] = threading.Event()
    discover.gates["beta"] = threading.Event()

    started = time.monotonic()
    registry = asyncio.run(server_mod.initialize_tool_registry())
    assert time.monotonic() - started < 1
    assert "bash" in registry
    assert not any(name.startswith("mcp__") for name in registry.list_tool_names())

    discover.gates["alpha"].set()
    discover.gates["beta"].set()
    assert wait_for(lambda: len([n for n in registry.list_tool_names() if n.startswith("mcp__")]) == 3)


def test_autoload_can_be_disabled(loader, discover, monkeypatch):
    monkeypatch.setattr(server_mod, "MCP_AUTOLOAD", False)
    asyncio.run(server_mod.initialize_tool_registry())
    time.sleep(0.05)
    assert discover.calls == []


# ---------- routes ----------


@pytest.fixture
def client(loader):
    # no `with`: the app's lifespan is not run
    return TestClient(app)


def test_status_route(client, loader):
    loader.ensure("alpha").result(5)
    assert wait_for(lambda: state(loader, "alpha") == "ready")
    statuses = {s["name"]: s for s in client.get("/api/v1/mcp/status").json()}
    assert statuses["alpha"]["state"] == "ready"
    assert statuses["alpha"]["tool_count"] == 2
    assert statuses["beta"]["state"] == "pending"
    assert client.get("/api/v1/mcp/servers/beta/status").json()["state"] == "pending"
    assert client.get("/api/v1/mcp/servers/nope/status").status_code == 404


def test_reload_route(client, loader, discover):
    resp = client.post("/api/v1/mcp/servers/alpha/reload")
    assert resp.status_code == 202
    assert wait_for(lambda: state(loader, "alpha") == "ready")
    assert discover.invalidated == ["alpha"]


def test_delete_route_forgets_server(client, loader):
    registry = ToolRegistry()
    loader.attach(registry)
    loader.start()
    assert wait_for(lambda: len(registry) == 3)
    assert client.delete("/api/v1/mcp/servers/alpha").status_code == 204
    assert registry.list_tool_names() == {"mcp__beta__b1"}


# ---------- cache ----------


def test_sqlite_cache_concurrent_writes(tmp_path):
    store = SqliteCacheStore(str(tmp_path / "cache.sqlite"))
    errors = []

    def work(i):
        try:
            for j in range(50):
                store.write_cache(f"k{i}-{j}", j)
                assert store.read_cache(f"k{i}-{j}") == j
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=work, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    store.delete_cache("k0-0")
    assert store.read_cache("k0-0") is None
