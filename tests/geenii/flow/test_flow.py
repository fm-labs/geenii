import json
import sys

import httpx
import pytest

from geenii.flow import Flow, FlowContext, FlowError, FlowStep, FlowStepSpec, StepEvent, register_step
from geenii.flow.steps.read_http import ReadHttpStep


@register_step("test_fail")
class FailStep(FlowStep):
    def process(self, input_data, ctx):
        raise ValueError("boom")


@register_step("test_abort")
class AbortStep(FlowStep):
    def process(self, input_data, ctx):
        ctx.abort("stop here")


class PlainStep(FlowStep):
    """Non-generator step, loaded by module path"""
    def process(self, input_data, ctx):
        return {"got": input_data}


def test_echo_passes_output_to_next_step():
    flow = Flow("t", [
        FlowStepSpec(id="a", type="echo", config={"message": "hello"}),
        FlowStepSpec(id="b", type="echo"),
    ])
    result = flow.run()
    assert result.status == "success"
    assert result.get("a").output == {"message": "hello"}
    assert result.get("b").output == {"message": {"message": "hello"}}


def test_references_and_interpolation():
    flow = Flow("t", [
        {"id": "a", "type": "echo", "config": {"message": {"name": "geenii", "items": [1, 2]}}},
        {"id": "b", "type": "echo", "config": {"message": "${a.message.items}"}},
        {"id": "c", "type": "echo", "config": {"message": "hi ${a.message.name} ${vars.x} ${input} $${a}"}},
    ], variables={"x": "X"})
    result = flow.run(input_data="IN")
    assert result.get("b").output["message"] == [1, 2]
    assert result.get("c").output["message"] == "hi geenii X IN ${a}"


def test_unknown_reference_fails_step():
    result = Flow("t", [{"id": "a", "type": "echo", "config": {"message": "${nope.x}"}}]).run()
    assert result.status == "failed"
    assert "nope.x" in result.get("a").error


def test_duplicate_and_reserved_ids():
    with pytest.raises(FlowError):
        Flow("t", [{"id": "a", "type": "echo"}, {"id": "a", "type": "echo"}])
    with pytest.raises(FlowError):
        Flow("t", [{"id": "input", "type": "echo"}])


def test_on_error_stop_skips_remaining():
    result = Flow("t", [
        {"id": "a", "type": "test_fail"},
        {"id": "b", "type": "echo"},
    ]).run()
    assert result.status == "failed"
    assert result.get("a").error == "ValueError: boom"
    assert result.get("b").status == "skipped"


def test_on_error_continue():
    result = Flow("t", [
        {"id": "a", "type": "test_fail", "on_error": "continue"},
        {"id": "b", "type": "echo", "config": {"message": "still here"}},
    ]).run()
    assert result.status == "failed"
    assert result.get("b").status == "success"


def test_abort():
    result = Flow("t", [
        {"id": "a", "type": "test_abort"},
        {"id": "b", "type": "echo"},
    ]).run()
    assert result.status == "aborted"
    assert result.get("a").error == "stop here"
    assert result.get("b").status == "skipped"


def test_unknown_type_and_module_path():
    assert Flow("t", [{"id": "a", "type": "does_not_exist"}]).run().status == "failed"
    result = Flow("t", [{"id": "a", "type": f"{__name__}:PlainStep"}]).run(input_data=1)
    assert result.output == {"got": 1}


def test_events():
    events: list[StepEvent] = []
    Flow("t", [{"id": "a", "type": "echo", "config": {"message": "m"}}]).run(on_event=events.append)
    assert [(e.type, e.step_id) for e in events] == [("step.start", "a"), ("log", "a"), ("step.end", "a")]


def test_execute_command():
    result = Flow("t", [
        {"id": "a", "type": "execute_command", "config": {"command": [sys.executable, "-c", "print('out', end='')"]}},
        {"id": "b", "type": "execute_command", "config": {"command": "echo ${a.stdout} | tr a-z A-Z", "shell": True}},
        {"id": "c", "type": "execute_command", "config": {"command": "false", "check": True}},
    ]).run()
    assert result.get("a").output == {"stdout": "out", "stderr": "", "rc": 0}
    assert result.get("b").output["stdout"].strip() == "OUT"
    assert result.get("c").status == "failed"


def test_execute_script_receives_input_on_stdin():
    script = """
        import json, sys
        data = json.load(sys.stdin)
        print(json.dumps({"doubled": data["n"] * 2}))
    """
    result = Flow("t", [
        {"id": "a", "type": "execute_script", "config": {"script": script, "json_output": True}},
    ]).run(input_data={"n": 21})
    assert result.status == "success", result.get("a").error
    assert result.output["result"] == {"doubled": 42}


def test_read_http(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["q"] == "x"
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr(ReadHttpStep, "transport", httpx.MockTransport(handler))
    result = Flow("t", [
        {"id": "a", "type": "read_http", "config": {"url": "http://test/api", "params": {"q": "x"}}},
    ]).run()
    assert result.status == "success", result.get("a").error
    assert result.output["status"] == 200
    assert result.output["data"] == {"ok": True}


def test_from_file(tmp_path):
    path = tmp_path / "flow.json"
    path.write_text(json.dumps({"name": "f", "steps": [{"id": "a", "type": "echo", "config": {"message": "x"}}]}))
    assert Flow.from_file(path).run().output == {"message": "x"}

    toml = tmp_path / "flow.toml"
    toml.write_text('name = "f"\n[[steps]]\nid = "a"\ntype = "echo"\nconfig = { message = "y" }\n')
    assert Flow.from_file(toml).run().output == {"message": "y"}


def test_context_lookup_attribute_and_index():
    ctx = FlowContext("t")
    ctx.results["a"] = {"list": [{"v": 1}]}
    assert ctx.lookup("a.list.0.v") == 1


# --- DAG: edges and `after` ---

def _order(result):
    return [s.step_id for s in result.steps]


def test_no_edges_runs_in_insertion_order():
    flow = Flow("t", [{"id": "a", "type": "echo"}, {"id": "b", "type": "echo"}, {"id": "c", "type": "echo"}])
    assert [(e.from_step, e.to_step) for e in flow.edges] == [("a", "b"), ("b", "c")]


def test_edges_define_order():
    flow = Flow("t", [
        {"id": "c", "type": "echo"},
        {"id": "b", "type": "echo"},
        {"id": "a", "type": "echo", "config": {"message": "A"}},
    ], edges=[("a", "b"), {"from_step": "b", "to_step": "c"}])
    result = flow.run()
    assert _order(result) == ["a", "b", "c"]
    assert result.get("c").output == {"message": {"message": {"message": "A"}}}


def test_after_infers_edges():
    flow = Flow("t", [
        {"id": "b", "type": "echo", "after": "a"},
        {"id": "a", "type": "echo", "config": {"message": "A"}},
    ])
    assert [(e.from_step, e.to_step) for e in flow.edges] == [("a", "b")]
    assert _order(flow.run()) == ["a", "b"]


def test_roots_get_flow_input_and_join_gets_dict():
    flow = Flow("t", [
        {"id": "left", "type": "echo"},
        {"id": "right", "type": "echo", "config": {"message": "R"}},
        {"id": "join", "type": "echo", "after": ["left", "right"]},
    ])
    result = flow.run(input_data="IN")
    assert result.get("left").output == {"message": "IN"}
    assert result.get("join").output == {"message": {"left": {"message": "IN"}, "right": {"message": "R"}}}


def test_add_edge_variants_and_dedupe():
    flow = Flow("t", [{"id": "a", "type": "echo"}, {"id": "b", "type": "echo", "after": "a"}])
    flow.add_edge("a", "b")
    flow.add_edge(("a", "b"))
    assert len(flow.edges) == 1
    with pytest.raises(FlowError):
        flow.add_edge("a", "a")


def test_invalid_graph_raises():
    with pytest.raises(FlowError, match="unknown step 'x'"):
        Flow("t", [{"id": "a", "type": "echo", "after": "x"}]).run()
    with pytest.raises(FlowError, match="Cycle"):
        Flow("t", [{"id": "a", "type": "echo", "after": "b"}, {"id": "b", "type": "echo", "after": "a"}]).run()


def test_continue_in_dag_passes_none_downstream():
    flow = Flow("t", [
        {"id": "a", "type": "test_fail", "on_error": "continue"},
        {"id": "b", "type": "echo", "after": "a"},
        {"id": "c", "type": "echo", "config": {"message": "independent"}},
    ])
    result = flow.run()
    assert result.status == "failed"
    assert result.get("b").output == {"message": None}
    assert result.get("c").status == "success"


def test_edges_from_toml(tmp_path):
    toml = tmp_path / "flow.toml"
    toml.write_text(
        'name = "f"\n'
        'edges = [{ from_step = "a", to_step = "b" }]\n'
        '[[steps]]\nid = "b"\ntype = "echo"\n'
        '[[steps]]\nid = "a"\ntype = "echo"\nconfig = { message = "x" }\n'
    )
    result = Flow.from_file(toml).run()
    assert _order(result) == ["a", "b"]
    assert result.output == {"message": {"message": "x"}}
