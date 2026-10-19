"""
Read-only info commands ("/self", "/usage", ...): they answer from the agent's own state without calling the model.

The reply is a markdown assistant message that is *not* added to the agent's memory, so it never ends up
in the context of later turns (and is gone when the conversation is reloaded).
"""
from __future__ import annotations

import glob
import json
import logging
import os
import re
from collections import Counter
from typing import Callable, Iterator, TYPE_CHECKING

import pydantic

if TYPE_CHECKING:
    from geenii.agent.base_agent import BaseAgent

from geenii.agent.base import BaseAgentTask
from geenii.chat_models import TextContent
from geenii.config import GEENII_CACHE_DIR
from geenii.datamodels import ModelMessage, Usage

logger = logging.getLogger(__name__)

# context ids get a "-<n>" suffix per /compact (see MemoryCompactionTask)
_GENERATION_SUFFIX = re.compile(r"(-\d+)+$")


def _cell(value) -> str:
    """Make a value safe for a markdown table cell."""
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ").strip()


def _table(headers: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(_cell(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)


def _fields(rows: list[list]) -> str:
    """Key/value pairs as a markdown list."""
    return "\n".join(f"- **{key}:** {value}" for key, value in rows)


def _first_line(text: str | None, limit: int = 120) -> str:
    line = (text or "").strip().split("\n", 1)[0]
    return line if len(line) <= limit else line[:limit - 1] + "…"


def _root_context_id(context_id: str) -> str:
    return _GENERATION_SUFFIX.sub("", context_id)


def _compactions(context_id: str) -> int:
    match = re.search(r"-(\d+)$", context_id)
    return int(match.group(1)) if match else 0


_builtin_tool_registry = None


def _builtin_tools():
    """Built-in tool definitions, for descriptions of allowed tools the agent's own registry does not hold."""
    global _builtin_tool_registry
    if _builtin_tool_registry is None:
        from geenii.tool.registry import ToolRegistry
        from geenii.tools import init_builtin_tools
        _builtin_tool_registry = ToolRegistry()
        init_builtin_tools(_builtin_tool_registry)
    return _builtin_tool_registry


def _tool_description(agent: "BaseAgent", name: str) -> str | None:
    for registry in (agent.tools, _builtin_tools()):
        if registry.has(name):
            return registry.get(name).description
    return None


def _usage_summary(agent: "BaseAgent") -> str:
    """The agent's in-memory usage counters (since this agent instance was created)."""
    calls = getattr(agent, "model_calls", 0)
    if not calls:
        return "no model calls yet"
    usage = agent.usage
    text = (f"{usage.total_tokens:,} tokens ({usage.input_tokens:,} in, {usage.output_tokens:,} out) "
            f"in {calls} model call{'s' if calls != 1 else ''}")
    if usage.cache_read_input_tokens:
        text += f", {usage.cache_read_input_tokens:,} input tokens from the cache"
    return text + " since the agent was started"


# -- reports ------------------------------------------------------------------

def report_self(agent: "BaseAgent", args: str) -> str:
    skills = sorted(agent.skills.names())
    active = set(agent.active_skills)
    rows = [
        ["Name", agent.name],
        ["Class", f"{agent.__class__.__module__}.{agent.__class__.__name__}"],
        ["Model", f"`{agent.model}`"],
        ["Conversation", f"`{agent.context_id}`"],
        ["Memory", f"{agent.memory.__class__.__name__}, {len(agent.message_history)} messages"],
        ["Tool approval", agent.hitl.__class__.__name__ if agent.hitl else "none"],
        ["Tools", f"{len(agent.allowed_tools)} allowed"],
        ["MCP servers", ", ".join(sorted(agent.mcp_servers)) or "none"],
        ["Skills", ", ".join(f"**{s}** (active)" if s in active else s for s in skills) or "none loaded"],
        ["Usage", _usage_summary(agent)],
    ]
    text = f"### {agent.name}\n\n"
    if agent.description:
        text += f"{agent.description.strip()}\n\n"
    return text + _fields(rows)


def report_usage(agent: "BaseAgent", args: str) -> str:
    root = _root_context_id(agent.context_id)
    pattern = re.compile(rf"^{re.escape(root)}(-\d+)*$")
    per_model: dict[str, Counter] = {}
    per_task: dict[str, Counter] = {}
    for path in sorted(glob.glob(os.path.join(GEENII_CACHE_DIR, "logs", "ai-usage-*.log"))):
        try:
            with open(path, "r") as f:
                for line in f:
                    if root not in line:  # cheap pre-filter before parsing
                        continue
                    try:
                        entry = json.loads(line)
                    except ValueError:
                        continue
                    if not pattern.match(str(entry.get("context_id") or "")):
                        continue
                    calls = Counter(calls=1, failed=1 if entry.get("error") else 0)
                    try:
                        usage = Usage.from_log_entry(entry)  # converts older log conventions
                    except pydantic.ValidationError:
                        usage = Usage()  # malformed usage: count the call, without tokens
                    for key, value in usage.model_dump(exclude_none=True).items():
                        if key.endswith("tokens"):
                            calls[key] += value
                    model = f"{entry.get('provider')}:{entry.get('model')}"
                    per_model.setdefault(model, Counter()).update(calls)
                    # lines written before source/task were logged have neither
                    per_task.setdefault(entry.get("task") or "untagged", Counter()).update(calls)
        except OSError as e:
            logger.warning(f"Could not read usage log {path}: {e}")

    if not per_model:
        return "### Usage\n\nNo model calls recorded for this conversation yet."

    def rows(counters: dict[str, Counter], fmt: str) -> list[list]:
        result = [[fmt.format(k), c["calls"], c["input_tokens"], c["output_tokens"], c["total_tokens"]]
                  for k, c in sorted(counters.items())]
        if len(counters) > 1:
            total = sum(counters.values(), Counter())
            result.append(["**Total**", total["calls"], total["input_tokens"], total["output_tokens"], total["total_tokens"]])
        return result

    columns = ["Calls", "Input tokens", "Output tokens", "Total"]
    text = "### Usage\n\n" + _table(["Model", *columns], rows(per_model, "`{}`"))
    if len(per_task) > 1:
        text += "\n\n**By purpose**\n\n" + _table(["Task", *columns], rows(per_task, "{}"))
    total = sum(per_model.values(), Counter())
    if total["failed"]:
        text += f"\n\n{total['failed']} of {total['calls']} calls failed; they used no tokens."
    cache_read, cache_write = total["cache_read_input_tokens"], total["cache_creation_input_tokens"]
    if cache_read or cache_write:
        share = f" ({cache_read * 100 // total['input_tokens']}%)" if total["input_tokens"] else ""
        text += f"\n\n{cache_read:,} of {total['input_tokens']:,} input tokens{share} were read from the prompt cache"
        text += f"; {cache_write:,} were written to it." if cache_write else "."
    text += "\n\nCounts all of the agent's model calls in this conversation, across compactions. Handoffs to other agents (`@agent`) are not included."
    return text


def report_models(agent: "BaseAgent", args: str) -> str:
    from geenii.ai import enumerate_models
    models = enumerate_models()
    if not models:
        return "### Models\n\nNo configured provider returned any models."
    by_provider: dict[str, list] = {}
    for m in sorted(models, key=lambda m: (m.provider, m.name)):
        by_provider.setdefault(m.provider, []).append(m)

    text = f"### Models ({len(models)})\n\nCurrent: `{agent.model}`\n"
    for provider, items in by_provider.items():
        localities = sorted({m.locality for m in items})
        names = [f"**`{m.name}`**" if f"{provider}:{m.name}" == agent.model else f"`{m.name}`" for m in items]
        text += f"\n- **{provider}** ({', '.join(localities)}, {len(items)}): {', '.join(names)}"
    if agent.model not in {f"{m.provider}:{m.name}" for m in models}:
        text += f"\n\nThe agent's model `{agent.model}` is not in this list."
    return text


def report_tools(agent: "BaseAgent", args: str) -> str:
    names = sorted(agent.allowed_tools)
    if not names:
        return "### Tools\n\nThis agent has no tools."
    builtin, mcp, missing = [], {}, []
    for name in names:
        description = _tool_description(agent, name)
        if description is None:
            missing.append(name)
        elif name.startswith("mcp__"):
            _, server, tool = name.split("__", 2) if name.count("__") >= 2 else ("", "?", name)
            mcp.setdefault(server, []).append([f"`{tool}`", _first_line(description)])
        else:
            builtin.append([f"`{name}`", _first_line(description)])

    text = f"### Tools ({len(names)})"
    if builtin:
        text += "\n\n**Built-in**\n\n" + _table(["Tool", "Description"], builtin)
    for server, rows in sorted(mcp.items()):
        text += f"\n\n**MCP: {server}**\n\n" + _table(["Tool", "Description"], rows)
    if missing:
        text += "\n\n**Not available** (configured but not loaded): " + ", ".join(f"`{n}`" for n in missing)
    return text


def report_context(agent: "BaseAgent", args: str) -> str:
    messages = list(agent.message_history)
    roles = Counter(m.role for m in messages)
    chars = sum(len(m.to_text()) for m in messages) + len(agent.system_prompt or "")
    rows = [
        ["Conversation", f"`{agent.context_id}`"],
        ["Compactions", _compactions(agent.context_id)],
        ["Messages", f"{len(messages)}"
                     + (" (" + ", ".join(f"{count} {role}" for role, count in sorted(roles.items())) + ")" if roles else "")],
        ["System prompt", f"{len(agent.system_prompt or '')} characters"],
        ["Estimated tokens", f"~{chars // 4}"],
    ]
    text = "### Context\n\n" + _fields(rows)
    text += "\n\nThe token estimate assumes about 4 characters per token. Use `/compact` to summarise or `/clear` to start over."
    return text


def report_help(agent: "BaseAgent", args: str) -> str:
    commands = getattr(agent, "BUILTIN_COMMANDS", {})
    rows = [[f"`/{name}`", description] for name, description in commands.items()]
    for name in sorted(agent.skills.names()):
        if name.lower() in commands:
            continue
        skill = agent.skills.get(name)
        rows.append([f"`/{name}`", f"Skill: {_first_line(skill.description if skill else '')}"])
    text = "### Commands\n\n" + _table(["Command", "Description"], rows)
    text += ("\n\n**Other prefixes**\n\n"
             "- `@agent message`: hand the message to another agent\n"
             "- `:tool key=value …`: call a tool directly")
    return text


# name -> (description, report)
INFO_COMMANDS: dict[str, tuple[str, Callable[["BaseAgent", str], str]]] = {
    "self": ("Show this agent's model, conversation, tools and skills", report_self),
    "usage": ("Show the tokens used in this conversation", report_usage),
    "models": ("List the available models", report_models),
    "tools": ("List this agent's tools", report_tools),
    "context": ("Show the size of the conversation memory", report_context),
    "help": ("List all commands", report_help),
}


class InfoCommandTask(BaseAgentTask):
    """Answer an info command with a markdown report. The reply is not stored in memory."""

    def __init__(self, agent: "BaseAgent", command: str, args: str = ""):
        super().__init__(agent)
        self.command = command
        self.args = args

    def execute(self) -> Iterator[ModelMessage]:
        _, report = INFO_COMMANDS[self.command]
        yield ModelMessage(role="assistant", content=[TextContent(text=report(self.agent, self.args))])
