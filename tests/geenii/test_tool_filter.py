"""Tests for ToolFilter and ToolFilterSet."""

import pytest
from geenii.tool.tool_filter import ToolFilter, ToolFilterSet


class TestToolFilterParse:
    def test_plain_tool_name(self):
        f = ToolFilter.parse("bash")
        assert f.tool_name == "bash"
        assert f.param is None
        assert f.pattern is None

    def test_parameterized_filter(self):
        f = ToolFilter.parse("Bash(command:uname *)")
        assert f.tool_name == "Bash"
        assert f.param == "command"
        assert f.pattern == "uname *"

    def test_wildcard_pattern(self):
        f = ToolFilter.parse("Bash(command:*)")
        assert f.tool_name == "Bash"
        assert f.param == "command"
        assert f.pattern == "*"

    def test_prefix_pattern(self):
        f = ToolFilter.parse("Bash(uname:*)")
        assert f.tool_name == "Bash"
        assert f.param == "uname"
        assert f.pattern == "*"


class TestToolFilterAllows:
    def test_plain_allows_any_args(self):
        f = ToolFilter.parse("bash")
        assert f.allows("bash", {"command": "rm -rf /"})
        assert f.allows("bash", {})
        assert f.allows("bash")

    def test_plain_rejects_wrong_tool(self):
        f = ToolFilter.parse("bash")
        assert not f.allows("python", {"command": "print(1)"})

    def test_case_insensitive_tool_name(self):
        f = ToolFilter.parse("Bash(command:uname *)")
        assert f.allows("bash", {"command": "uname -a"})
        assert f.allows("BASH", {"command": "uname -a"})

    def test_parameterized_allows_matching(self):
        f = ToolFilter.parse("Bash(command:uname *)")
        assert f.allows("bash", {"command": "uname -a"})
        assert f.allows("bash", {"command": "uname -r"})

    def test_parameterized_rejects_non_matching(self):
        f = ToolFilter.parse("Bash(command:uname *)")
        assert not f.allows("bash", {"command": "rm -rf /"})
        assert not f.allows("bash", {"command": "ls -la"})

    def test_wildcard_allows_everything(self):
        f = ToolFilter.parse("Bash(command:*)")
        assert f.allows("bash", {"command": "anything"})

    def test_missing_param_rejects(self):
        f = ToolFilter.parse("Bash(command:uname *)")
        assert not f.allows("bash", {})
        assert not f.allows("bash", None)


class TestToolFilterSet:
    def test_empty_allows_all(self):
        fs = ToolFilterSet()
        assert fs.allows("bash", {"command": "anything"})

    def test_any_match_allows(self):
        fs = ToolFilterSet.parse("Bash(command:uname *), Bash(command:hostname *)")
        assert fs.allows("bash", {"command": "uname -a"})
        assert fs.allows("bash", {"command": "hostname -f"})
        assert not fs.allows("bash", {"command": "rm -rf /"})

    def test_tool_names(self):
        fs = ToolFilterSet.parse("Bash(command:uname *), python, read")
        assert fs.tool_names() == {"bash", "python", "read"}

    def test_from_list(self):
        items = [
            "Bash(command:uname *), Bash(command:hostname *)",
            "read",
            "write",
        ]
        fs = ToolFilterSet.from_list(items)
        assert len(fs) == 4
        assert fs.tool_names() == {"bash", "read", "write"}

    def test_has_argument_filters(self):
        fs = ToolFilterSet.parse("Bash(command:uname *), python, read")
        assert fs.has_argument_filters("bash")
        assert not fs.has_argument_filters("python")
        assert not fs.has_argument_filters("read")

    def test_parse_multiline_yaml_style(self):
        raw = (
            "Bash(command:uname *), Bash(command:hostname *), "
            "Bash(command:arch *), Bash(command:uptime *), "
            "Bash(command:date *)"
        )
        fs = ToolFilterSet.parse(raw)
        assert len(fs) == 5
        assert fs.allows("bash", {"command": "uname -a"})
        assert fs.allows("bash", {"command": "date +%Y"})
        assert not fs.allows("bash", {"command": "curl http://evil.com"})

    def test_mixed_plain_and_parameterized(self):
        fs = ToolFilterSet.parse("Bash(command:uname *), read, write")
        assert fs.allows("read", {})
        assert fs.allows("write", {"path": "/any"})
        assert fs.allows("bash", {"command": "uname -a"})
        assert not fs.allows("bash", {"command": "rm -rf /"})


class TestToolFilterStr:
    def test_plain(self):
        assert str(ToolFilter.parse("bash")) == "bash"

    def test_parameterized(self):
        assert str(ToolFilter.parse("Bash(command:uname *)")) == "Bash(command:uname *)"
