import json

import pytest

from geenii.tool.common import ToolCallContext, ToolCallResult
from geenii.tool.python import PythonFunctionTool

CTX = ToolCallContext(cwd=".")


def invoke(value):
    return PythonFunctionTool(name="t", handler=lambda: value).invoke(args={}, ctx=CTX)


@pytest.mark.parametrize("value, text", [
    ("hi", "hi"),
    ("", ""),
    (None, ""),
    (3, "3"),
    (1.5, "1.5"),
    (True, "True"),
    (b"bytes \xff", "bytes �"),
])
def test_scalar_results_become_text(value, text):
    assert invoke(value) == ToolCallResult(text=text)


def test_dict_is_structured_content_and_json_text():
    result = invoke({"a": 1, "b": [1, 2]})
    assert result.structured_content == {"a": 1, "b": [1, 2]}
    assert json.loads(result.text) == {"a": 1, "b": [1, 2]}
    assert result.is_error is False


@pytest.mark.parametrize("value", [[1, "x"], (1, "x")])
def test_list_and_tuple_are_json_text(value):
    result = invoke(value)
    assert json.loads(result.text) == [1, "x"]
    # structured content must be an object
    assert result.structured_content is None


def test_values_that_are_not_json_are_stringified():
    class Thing:
        def __str__(self):
            return "thing"

    assert json.loads(invoke({"t": Thing()}).text) == {"t": "thing"}
    assert invoke(Thing()).text == "thing"


def test_tool_call_result_is_returned_as_is():
    expected = ToolCallResult(text="failed", structured_content={"error": "x"}, is_error=True)
    assert invoke(expected) is expected


def test_async_handler_result_is_mapped_too():
    async def handler():
        return {"ok": True}

    result = PythonFunctionTool(name="t", handler=handler).invoke(args={}, ctx=CTX)
    assert result.structured_content == {"ok": True}
