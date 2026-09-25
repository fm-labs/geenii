"""Tool filtering with argument-level restrictions.

Supports Claude-style allowed-tools syntax:
  - "bash"                    → allow tool "bash" with any arguments
  - "Bash(uname:*)"          → allow tool "bash" only when the first arg starts with "uname"
  - "Bash(command:uname *)"  → allow tool "bash" only when "command" arg starts with "uname "
  - "Bash(command:*)"        → allow tool "bash" with any "command" value (same as plain "bash")

The syntax is:  ToolName(param:pattern)
  - ToolName is case-insensitive for matching
  - param is the argument key to check
  - pattern uses fnmatch-style wildcards (* matches anything)
"""

from __future__ import annotations

import fnmatch
import logging
import re
import shlex
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_FILTER_RE = re.compile(
    r'^(?P<tool>[A-Za-z_][A-Za-z0-9_-]*)'
    r'(?:\((?P<param>[A-Za-z_][A-Za-z0-9_]*):'
    r'(?P<pattern>[^)]*)\))?$'
)


@dataclass(frozen=True)
class ToolFilter:
    """A single tool-access rule, optionally restricting one argument."""

    tool_name: str
    param: str | None = None
    pattern: str | None = None

    def matches_tool(self, tool_name: str) -> bool:
        return self.tool_name.lower() == tool_name.lower()

    def allows(self, tool_name: str, arguments: dict | None = None) -> bool:
        if not self.matches_tool(tool_name):
            return False
        if self.param is None:
            return True
        if arguments is None:
            return False
        value = arguments.get(self.param, "")
        if not isinstance(value, str):
            value = str(value)
        return fnmatch.fnmatch(value, self.pattern)

    @staticmethod
    def parse(raw: str) -> ToolFilter:
        raw = raw.strip()
        m = _FILTER_RE.match(raw)
        if not m:
            return ToolFilter(tool_name=raw)
        tool = m.group("tool")
        param = m.group("param")
        pattern = m.group("pattern")
        if param is None:
            return ToolFilter(tool_name=tool)
        return ToolFilter(tool_name=tool, param=param, pattern=pattern.strip())

    def __str__(self) -> str:
        if self.param:
            return f"{self.tool_name}({self.param}:{self.pattern})"
        return self.tool_name


@dataclass
class ToolFilterSet:
    """A collection of ToolFilter rules. A tool call is allowed if ANY rule permits it."""

    filters: list[ToolFilter] = field(default_factory=list)

    def tool_names(self) -> set[str]:
        return {f.tool_name.lower() for f in self.filters}

    def allows(self, tool_name: str, arguments: dict | None = None) -> bool:
        if not self.filters:
            return True
        for f in self.filters:
            if f.allows(tool_name, arguments):
                return True
        return False

    def has_argument_filters(self, tool_name: str) -> bool:
        for f in self.filters:
            if f.matches_tool(tool_name) and f.param is not None:
                return True
        return False

    @staticmethod
    def _tokenize(raw: str) -> list[str]:
        """Split a raw string into individual filter expressions, respecting parentheses."""
        tokens = []
        current = []
        depth = 0
        for ch in raw:
            if ch == '(':
                depth += 1
                current.append(ch)
            elif ch == ')':
                depth -= 1
                current.append(ch)
                if depth == 0:
                    tokens.append(''.join(current).strip())
                    current = []
            elif ch in (',', ' ', '\t', '\n') and depth == 0:
                piece = ''.join(current).strip()
                if piece:
                    tokens.append(piece)
                current = []
            else:
                current.append(ch)
        piece = ''.join(current).strip()
        if piece:
            tokens.append(piece)
        return tokens

    @staticmethod
    def parse(raw: str) -> ToolFilterSet:
        """Parse a comma-or-space-separated list of filter expressions."""
        filters = []
        for token in ToolFilterSet._tokenize(raw):
            filters.append(ToolFilter.parse(token))
        return ToolFilterSet(filters=filters)

    @staticmethod
    def from_list(items: list[str]) -> ToolFilterSet:
        filters = []
        for item in items:
            for token in ToolFilterSet._tokenize(item):
                filters.append(ToolFilter.parse(token))
        return ToolFilterSet(filters=filters)

    def __bool__(self) -> bool:
        return len(self.filters) > 0

    def __len__(self) -> int:
        return len(self.filters)
