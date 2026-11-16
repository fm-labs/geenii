"""
User plugins: Python packages loaded at runtime from the directories in the
user setting ``plugin_dirs`` (``~/.geenii/settings.json``). They are not part
of the built app.

Each sub-folder of a plugin dir that is an importable package (has an
``__init__.py``) is a plugin. If the package defines ``register(ctx)``, it is
called once with a :class:`PluginContext`, through which the plugin adds
agents and tools::

    # <plugin_dir>/myplugin/__init__.py
    from geenii.agent.registry import AgentSpec

    def register(ctx):
        ctx.tools.register_function(my_tool, name="my_tool", description="...", parameters={})
        ctx.add_agent(AgentSpec(name="myagent", model="ollama:qwen3:8b",
                                class_name="myplugin.agents.MyAgent", tools=["my_tool"]))

Plugin code runs with the full privileges of the geenii process. In the built
(Nuitka) app, plugins can only import modules that are bundled with the app.
"""

from __future__ import annotations

import importlib
import logging
import os
import pkgutil
import sys
import threading
from dataclasses import dataclass, field
from types import ModuleType

from geenii.agent.registry import AgentSpec
from geenii.config import read_user_settings
from geenii.tool.registry import ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class PluginContext:
    """What a plugin's ``register(ctx)`` gets to add things to."""

    plugin_name: str
    tools: ToolRegistry
    agents: dict[str, AgentSpec] = field(default_factory=dict)

    def add_agent(self, spec: AgentSpec) -> None:
        if spec.scope == "user":
            spec.scope = "global"
        self.agents[spec.name] = spec


@dataclass
class LoadedPlugin:
    name: str
    path: str
    module: ModuleType | None = None
    error: str | None = None


_lock = threading.Lock()
_loaded = False
_plugins: dict[str, LoadedPlugin] = {}
_agents: dict[str, AgentSpec] = {}
_tools = ToolRegistry()


def plugin_dirs() -> list[str]:
    dirs = []
    for _dir in read_user_settings().get("plugin_dirs", []) or []:
        _dir = os.path.abspath(os.path.expanduser(_dir))
        if not os.path.isdir(_dir):
            logger.warning(f"Plugin dir not found: {_dir}")
            continue
        dirs.append(_dir)
    return dirs


def _load_plugin(name: str, path: str) -> LoadedPlugin:
    plugin = LoadedPlugin(name=name, path=path)
    try:
        plugin.module = importlib.import_module(name)
        mod_file = getattr(plugin.module, "__file__", None) or ""
        if not os.path.abspath(mod_file).startswith(path + os.sep):
            # a module with the same name (stdlib, geenii, site-packages) shadows the plugin
            raise ImportError(f"'{name}' resolves to {mod_file}, not to the plugin in {path}")

        register = getattr(plugin.module, "register", None)
        if callable(register):
            ctx = PluginContext(plugin_name=name, tools=ToolRegistry())
            register(ctx)
            for tool in ctx.tools.list_tools():
                if _tools.has(tool.name):
                    logger.warning(f"Plugin '{name}' overrides tool '{tool.name}'")
                    _tools.unregister(tool.name)
                _tools.register(tool)
            for agent_name, spec in ctx.agents.items():
                if agent_name in _agents:
                    logger.warning(f"Plugin '{name}' overrides agent '{agent_name}'")
                _agents[agent_name] = spec
            logger.info(
                f"Plugin '{name}' loaded from {path}: "
                f"{len(ctx.agents)} agent(s), {len(ctx.tools)} tool(s)"
            )
        else:
            logger.info(f"Plugin '{name}' loaded from {path} (no register())")
    except Exception as e:
        plugin.error = f"{type(e).__name__}: {e}"
        logger.exception(f"Failed to load plugin '{name}' from {path}")
    return plugin



def load_plugins() -> dict[str, LoadedPlugin]:
    """Discover and load all plugins once per process. Safe to call repeatedly."""
    global _loaded
    with _lock:
        if _loaded:
            return _plugins
        _loaded = True
        for _dir in plugin_dirs():
            if _dir not in sys.path:
                sys.path.append(_dir)
            for info in pkgutil.iter_modules([_dir]):
                if not info.ispkg:
                    continue
                if info.name in _plugins:
                    logger.warning(f"Plugin '{info.name}' in {_dir} ignored, already loaded from {_plugins[info.name].path}")
                    continue
                _plugins[info.name] = _load_plugin(info.name, _dir)
        return _plugins


def plugin_agents() -> dict[str, AgentSpec]:
    """Agent specs added by plugins (copies, so callers may modify them)."""
    load_plugins()
    return {name: spec.model_copy(deep=True) for name, spec in _agents.items()}


def plugin_tools() -> ToolRegistry:
    """Tools added by plugins."""
    load_plugins()
    return _tools
