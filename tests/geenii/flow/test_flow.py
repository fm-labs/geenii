import json
import sys
import threading
import time

import httpx
import pytest

from geenii.flow import (
    Flow,
    FlowContext,
    FlowError,
    FlowProcessor,
    FlowSnapshot,
    FlowStepSpec,
    StepEvent,
    register_processor,
)
from geenii.flow.processor.read_http import ReadHttpProcessor


@register_processor("test_fail")
class FailProcessor(FlowProcessor):
    def process(self, input_data, ctx):
        raise ValueError("boom")


@register_processor("test_abort")
class AbortProcessor(FlowProcessor):
    def process(self, input_data, ctx):
        ctx.abort("stop here")


class PlainProcessor(FlowProcessor):
    """Non-generator step, loaded by module path"""

    def process(self, input_data, ctx):
        return {"got": input_data}


def test_echo_passes_output_to_next_step():
    flow = Flow(
        "t",
        [
            FlowStepSpec(id="a", processor="echo", config={"message": "hello"}),
            FlowStepSpec(id="b", processor="echo", depends_on="a"),
        ],
    )
    result = flow.run()
    assert result.status == "success"
    assert result.get("a").output == {"message": "hello"}
    assert result.get("b").output == {"message": {"message": "hello"}}


def test_references_and_interpolation():
    flow = Flow(
        "t",
        [
            {
                "id": "a",
                "processor": "echo",
                "config": {"message": {"name": "geenii", "items": [1, 2]}},
            },
            {
                "id": "b",
                "processor": "echo",
                "depends_on": "a",
                "config": {"message": "${a.message.items}"},
            },
            {
                "id": "c",
                "processor": "echo",
                "depends_on": "a",
                "config": {"message": "hi ${a.message.name} ${vars.x} ${input} $${a}"},
            },
        ],
        variables={"x": "X"},
    )
    result = flow.run(input_data="IN")
    assert result.get("b").output["message"] == [1, 2]
    assert result.get("c").output["message"] == "hi geenii X IN ${a}"


def test_unknown_reference_fails_step():
    result = Flow("t", [{"id": "a", "processor": "echo", "config": {"message": "${nope.x}"}}]).run()
    assert result.status == "failed"
    assert "nope.x" in result.get("a").error


def test_duplicate_and_reserved_ids():
    with pytest.raises(FlowError):
        Flow("t", [{"id": "a", "processor": "echo"}, {"id": "a", "processor": "echo"}])
    with pytest.raises(FlowError):
        Flow("t", [{"id": "input", "processor": "echo"}])


def test_on_error_stop_skips_remaining():
    result = Flow(
        "t",
        [
            {"id": "a", "processor": "test_fail"},
            {"id": "b", "processor": "echo"},
        ],
    ).run()
    assert result.status == "failed"
    assert result.get("a").error == "ValueError: boom"
    assert result.get("b").status == "skipped"


def test_on_error_continue():
    result = Flow(
        "t",
        [
            {"id": "a", "processor": "test_fail", "on_error": "continue"},
            {"id": "b", "processor": "echo", "config": {"message": "still here"}},
        ],
    ).run()
    assert result.status == "failed"
    assert result.get("b").status == "success"


def test_abort():
    result = Flow(
        "t",
        [
            {"id": "a", "processor": "test_abort"},
            {"id": "b", "processor": "echo"},
        ],
    ).run()
    assert result.status == "aborted"
    assert result.get("a").error == "stop here"
    assert result.get("b").status == "skipped"


def test_unknown_type_and_module_path():
    assert Flow("t", [{"id": "a", "processor": "does_not_exist"}]).run().status == "failed"
    result = Flow("t", [{"id": "a", "processor": f"{__name__}:PlainProcessor"}]).run(input_data=1)
    assert result.output == {"got": 1}


def test_events():
    events: list[StepEvent] = []
    Flow("t", [{"id": "a", "processor": "echo", "config": {"message": "m"}}]).run(on_event=events.append)
    assert [(e.type, e.step_id) for e in events] == [
        ("step.start", "a"),
        ("log", "a"),
        ("step.end", "a"),
    ]


def test_execute_command():
    result = Flow(
        "t",
        [
            {
                "id": "a",
                "processor": "execute_command",
                "config": {"command": [sys.executable, "-c", "print('out', end='')"]},
            },
            {
                "id": "b",
                "processor": "execute_command",
                "depends_on": "a",
                "config": {"command": "echo ${a.stdout} | tr a-z A-Z", "shell": True},
            },
            {
                "id": "c",
                "processor": "execute_command",
                "config": {"command": "false", "check": True},
            },
        ],
    ).run()
    assert result.get("a").output == {"stdout": "out", "stderr": "", "rc": 0}
    assert result.get("b").output["stdout"].strip() == "OUT"
    assert result.get("c").status == "failed"


def test_execute_command_streams_output_lines():
    events: list[StepEvent] = []
    script = "import sys, time; print('one', flush=True); time.sleep(0.2); print('err', file=sys.stderr); print('two')"
    result = Flow(
        "t",
        [
            {
                "id": "a",
                "processor": "execute_command",
                "config": {"command": [sys.executable, "-c", script]},
            },
        ],
    ).run(on_event=lambda e: events.append((e, time.monotonic())))
    assert result.get("a").output == {
        "stdout": "one\ntwo\n",
        "stderr": "err\n",
        "rc": 0,
    }
    streamed = [(e.type, e.data) for e, _ in events if e.type in ("stdout", "stderr")]
    assert sorted(streamed) == [("stderr", "err"), ("stdout", "one"), ("stdout", "two")]
    # the first line arrives before the process exits
    first = next(t for e, t in events if e.data == "one")
    end = next(t for e, t in events if e.type == "step.end")
    assert end - first >= 0.15


def test_execute_command_timeout_kills_process():
    started = time.monotonic()
    result = Flow(
        "t",
        [
            {
                "id": "a",
                "processor": "execute_command",
                "config": {
                    "command": [sys.executable, "-c", "import time; time.sleep(10)"],
                    "timeout": 0.3,
                },
            },
        ],
    ).run()
    assert result.get("a").status == "failed"
    assert "TimeoutExpired" in result.get("a").error
    assert time.monotonic() - started < 5


def test_execute_script_receives_input_on_stdin():
    script = """
        import json, sys
        data = json.load(sys.stdin)
        print(json.dumps({"doubled": data["n"] * 2}))
    """
    result = Flow(
        "t",
        [
            {
                "id": "a",
                "processor": "execute_script",
                "config": {"script": script, "json_output": True},
            },
        ],
    ).run(input_data={"n": 21})
    assert result.status == "success", result.get("a").error
    assert result.output["result"] == {"doubled": 42}


def test_read_http(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["q"] == "x"
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr(ReadHttpProcessor, "transport", httpx.MockTransport(handler))
    result = Flow(
        "t",
        [
            {
                "id": "a",
                "processor": "read_http",
                "config": {"url": "http://test/api", "params": {"q": "x"}},
            },
        ],
    ).run()
    assert result.status == "success", result.get("a").error
    assert result.output["status"] == 200
    assert result.output["data"] == {"ok": True}


def test_from_file(tmp_path):
    path = tmp_path / "flow.json"
    path.write_text(
        json.dumps(
            {
                "name": "f",
                "steps": [{"id": "a", "processor": "echo", "config": {"message": "x"}}],
            }
        )
    )
    assert Flow.from_file(path).run().output == {"message": "x"}

    toml = tmp_path / "flow.toml"
    toml.write_text('name = "f"\n[[steps]]\nid = "a"\nprocessor = "echo"\nconfig = { message = "y" }\n')
    assert Flow.from_file(toml).run().output == {"message": "y"}

    yml = tmp_path / "flow.yml"
    yml.write_text(
        "name: f\nsteps:\n  - id: a\n    processor: echo\n    config:\n      message: ${vars.x}\nvars:\n  x: z\n"
    )
    assert Flow.from_file(yml).run().output == {"message": "z"}

    bad = tmp_path / "bad.yaml"
    bad.write_text("name: [")
    with pytest.raises(FlowError, match="Invalid YAML"):
        Flow.from_file(bad)


def test_to_dict_and_to_file_round_trip(tmp_path):
    flow = Flow(
        "f",
        [
            {"id": "a", "processor": "echo", "config": {"message": "${vars.x}"}},
            {"id": "b", "processor": "echo", "on_error": "continue"},
            {"id": "c", "processor": "echo", "depends_on": ["a"]},
        ],
        edges=[("a", "b")],
        variables={"x": "X"},
        max_workers=2,
    )
    assert flow.to_dict() == {
        "name": "f",
        "max_workers": 2,
        "vars": {"x": "X"},
        "edges": [{"from_step": "a", "to_step": "b"}],
        "steps": [
            {"id": "a", "processor": "echo", "config": {"message": "${vars.x}"}},
            {"id": "b", "processor": "echo", "on_error": "continue"},
            {"id": "c", "processor": "echo", "depends_on": ["a"]},
        ],
    }
    assert json.loads(flow.to_json()) == flow.to_dict()
    for name in ("flow.json", "flow.toml", "flow.yaml"):
        flow.to_file(tmp_path / name)
        assert Flow.from_file(tmp_path / name).to_dict() == flow.to_dict()
    with pytest.raises(FlowError):
        flow.to_file(tmp_path / "flow.xml")


def test_snapshots_during_and_after_run(tmp_path):
    flow = Flow(
        "f",
        [
            {"id": "a", "processor": "echo", "config": {"message": "m"}},
            {"id": "b", "processor": "echo", "depends_on": "a"},
        ],
    )
    snapshots: list[FlowSnapshot] = []
    result = flow.run(input_data={"n": 1}, snapshot=snapshots.append)
    assert [(s.status, [r.step_id for r in s.steps], s.pending) for s in snapshots] == [
        ("running", [], ["a", "b"]),
        ("running", ["a"], ["b"]),
        ("running", ["a", "b"], []),
        ("success", ["a", "b"], []),
    ]
    final = snapshots[-1]
    assert final.steps == result.steps
    assert final.input == {"n": 1}
    assert final.to_flow().to_dict() == flow.to_dict()

    path = tmp_path / "snap.json"
    flow.run(input_data=object(), snapshot=path)  # input that isn't JSON serializable is stored as str
    loaded = FlowSnapshot.load(path)
    assert loaded.status == "success"
    assert loaded.get("b").output == {"message": {"message": "m"}}
    assert isinstance(loaded.input, str)
    assert not list(tmp_path.glob(".*.tmp"))


def test_context_id():
    @register_processor("test_context_id")
    class ContextIdProcessor(FlowProcessor):
        def process(self, input_data, ctx):
            return ctx.id

    flow = Flow("f", [{"id": "a", "processor": "test_context_id"}])
    snapshots: list[FlowSnapshot] = []
    first, second = flow.run(snapshot=snapshots.append), flow.run()
    assert first.context_id and first.context_id != second.context_id
    assert first.output == first.context_id
    assert {s.context_id for s in snapshots} == {first.context_id}
    assert flow.run(context_id="run-1").context_id == "run-1"


def test_snapshot_error_does_not_stop_flow(tmp_path):
    result = Flow("f", [{"id": "a", "processor": "echo"}]).run(snapshot=tmp_path / "missing" / "snap.json")
    assert result.status == "success"


def test_context_lookup_attribute_and_index():
    ctx = FlowContext("t")
    ctx.results["a"] = {"list": [{"v": 1}]}
    assert ctx.lookup("a.list.0.v") == 1


# --- DAG: edges and `depends_on` ---


def _order(result):
    return [s.step_id for s in result.steps]


def test_check_references():
    flow = Flow(
        "t",
        [
            {
                "id": "a",
                "processor": "echo",
                "config": {"message": "${input} ${vars.x} $${b.literal}"},
            },
            {
                "id": "b",
                "processor": "echo",
                "depends_on": "a",
                "config": {"message": "${a.message}"},
            },
            # indirect dependency on 'a' is fine; nested config values are checked too
            {
                "id": "c",
                "processor": "echo",
                "depends_on": "b",
                "config": {"message": {"x": ["${a}", "${ b.message }"]}},
            },
            {
                "id": "d",
                "processor": "echo",
                "config": {"message": "${c.message} ${d} ${nope.x}"},
            },
        ],
    )
    assert flow.check_references() == [
        "Step 'd': reference '${c.message}': doesn't depend on 'c'; add it to depends_on",
        "Step 'd': reference '${d}': references itself",
        "Step 'd': reference '${nope.x}': unknown step 'nope'",
    ]
    assert flow.ancestors()["c"] == {"a", "b"}


def test_run_logs_reference_warnings(caplog):
    flow = Flow(
        "t",
        [
            {"id": "a", "processor": "echo"},
            {"id": "b", "processor": "echo", "config": {"message": "${a.message}"}},
        ],
    )
    with caplog.at_level("WARNING", logger="geenii.flow.flow"):
        assert flow.run().status == "success"  # sequential: 'a' happens to run first
    assert "Step 'b': reference '${a.message}': doesn't depend on 'a'" in caplog.text


def test_no_edges_are_independent_roots():
    flow = Flow(
        "t",
        [
            {"id": "a", "processor": "echo"},
            {"id": "b", "processor": "echo"},
            {"id": "c", "processor": "echo"},
        ],
    )
    assert flow.edges == []
    result = flow.run(input_data="in")
    assert _order(result) == ["a", "b", "c"]  # sequential: insertion order
    assert [r.output for r in result.steps] == [{"message": "in"}] * 3  # each root gets the flow input


def test_edges_define_order():
    flow = Flow(
        "t",
        [
            {"id": "c", "processor": "echo"},
            {"id": "b", "processor": "echo"},
            {"id": "a", "processor": "echo", "config": {"message": "A"}},
        ],
        edges=[("a", "b"), {"from_step": "b", "to_step": "c"}],
    )
    result = flow.run()
    assert _order(result) == ["a", "b", "c"]
    assert result.get("c").output == {"message": {"message": {"message": "A"}}}


def test_depends_on_infers_edges():
    flow = Flow(
        "t",
        [
            {"id": "b", "processor": "echo", "depends_on": "a"},
            {"id": "a", "processor": "echo", "config": {"message": "A"}},
        ],
    )
    assert [(e.from_step, e.to_step) for e in flow.edges] == [("a", "b")]
    assert _order(flow.run()) == ["a", "b"]


def test_roots_get_flow_input_and_join_gets_dict():
    flow = Flow(
        "t",
        [
            {"id": "left", "processor": "echo"},
            {"id": "right", "processor": "echo", "config": {"message": "R"}},
            {"id": "join", "processor": "echo", "depends_on": ["left", "right"]},
        ],
    )
    result = flow.run(input_data="IN")
    assert result.get("left").output == {"message": "IN"}
    assert result.get("join").output == {"message": {"left": {"message": "IN"}, "right": {"message": "R"}}}


def test_add_edge_variants_and_dedupe():
    flow = Flow(
        "t",
        [
            {"id": "a", "processor": "echo"},
            {"id": "b", "processor": "echo", "depends_on": "a"},
        ],
    )
    flow.add_edge("a", "b")
    flow.add_edge(("a", "b"))
    assert len(flow.edges) == 1
    with pytest.raises(FlowError):
        flow.add_edge("a", "a")


def test_invalid_graph_raises():
    with pytest.raises(FlowError, match="unknown step 'x'"):
        Flow("t", [{"id": "a", "processor": "echo", "depends_on": "x"}]).run()
    with pytest.raises(FlowError, match="Cycle"):
        Flow(
            "t",
            [
                {"id": "a", "processor": "echo", "depends_on": "b"},
                {"id": "b", "processor": "echo", "depends_on": "a"},
            ],
        ).run()


def test_continue_in_dag_passes_none_downstream():
    flow = Flow(
        "t",
        [
            {"id": "a", "processor": "test_fail", "on_error": "continue"},
            {"id": "b", "processor": "echo", "depends_on": "a"},
            {"id": "c", "processor": "echo", "config": {"message": "independent"}},
        ],
    )
    result = flow.run()
    assert result.status == "failed"
    assert result.get("b").output == {"message": None}
    assert result.get("c").status == "success"


def test_edges_from_toml(tmp_path):
    toml = tmp_path / "flow.toml"
    toml.write_text(
        'name = "f"\n'
        'edges = [{ from_step = "a", to_step = "b" }]\n'
        '[[steps]]\nid = "b"\nprocessor = "echo"\n'
        '[[steps]]\nid = "a"\nprocessor = "echo"\nconfig = { message = "x" }\n'
    )
    result = Flow.from_file(toml).run()
    assert _order(result) == ["a", "b"]
    assert result.output == {"message": {"message": "x"}}


# --- parallel execution ---


@register_processor("test_barrier")
class BarrierProcessor(FlowProcessor):
    """Waits until `parties` steps reach the barrier in ctx.vars; fails when they don't run concurrently"""

    def process(self, input_data, ctx):
        ctx.vars["barrier"].wait()
        return {"thread": threading.current_thread().name}


@register_processor("test_sleep")
class SleepProcessor(FlowProcessor):
    def process(self, input_data, ctx):
        time.sleep(self.config.get("seconds", 0.2))
        return {"stopping": ctx.stopping}


def _branches(n: int, processor: str = "test_barrier") -> list[dict]:
    steps = [{"id": "root", "processor": "echo", "config": {"message": "r"}}]
    steps += [{"id": f"b{i}", "processor": processor, "depends_on": "root"} for i in range(n)]
    steps += [{"id": "join", "processor": "echo", "depends_on": [f"b{i}" for i in range(n)]}]
    return steps


def test_parallel_branches_run_concurrently():
    flow = Flow(
        "t",
        _branches(3),
        variables={"barrier": threading.Barrier(3, timeout=2)},
        max_workers=3,
    )
    result = flow.run()
    assert result.status == "success", [s.error for s in result.steps]
    threads = {result.get(f"b{i}").output["thread"] for i in range(3)}
    assert len(threads) == 3 and all(t.startswith("flow-t") for t in threads)
    assert [s.step_id for s in result.steps] == ["root", "b0", "b1", "b2", "join"]
    assert set(result.get("join").output["message"]) == {"b0", "b1", "b2"}


def test_sequential_by_default():
    # with one worker the barrier can never be reached by 2 processor at once
    flow = Flow("t", _branches(2), variables={"barrier": threading.Barrier(2, timeout=0.2)})
    result = flow.run()
    assert result.get("b0").status == "failed"
    assert result.get("b1").status == "skipped"


def test_max_workers_override_and_limit():
    flow = Flow("t", _branches(2), variables={"barrier": threading.Barrier(2, timeout=2)})
    assert flow.run(max_workers=2).status == "success"
    # 3 branches, 2 workers: the third waits, so a barrier of 3 can't be reached
    flow = Flow(
        "t",
        _branches(3),
        variables={"barrier": threading.Barrier(3, timeout=0.2)},
        max_workers=2,
    )
    assert flow.run().status == "failed"
    with pytest.raises(FlowError):
        flow.run(max_workers=0)


def test_parallel_stop_lets_running_steps_finish():
    flow = Flow(
        "t",
        [
            {"id": "slow", "processor": "test_sleep", "config": {"seconds": 0.3}},
            {"id": "fail", "processor": "test_fail"},
            {"id": "after_slow", "processor": "echo", "depends_on": "slow"},
        ],
        max_workers=2,
    )
    result = flow.run()
    assert result.status == "failed"
    assert result.get("fail").status == "failed"
    assert result.get("slow").status == "success"
    assert result.get("slow").output == {"stopping": True}
    assert result.get("after_slow").status == "skipped"


def test_parallel_events_are_serialized():
    active = 0
    overlaps = []

    def on_event(event):
        nonlocal active
        active += 1
        overlaps.append(active)
        time.sleep(0.01)
        active -= 1

    flow = Flow("t", _branches(4, "test_sleep"), max_workers=4)
    assert flow.run(on_event=on_event).status == "success"
    assert max(overlaps) == 1


def test_max_workers_from_file(tmp_path):
    path = tmp_path / "flow.json"
    path.write_text(json.dumps({"name": "f", "max_workers": 4, "steps": [{"id": "a", "processor": "echo"}]}))
    assert Flow.from_file(path).max_workers == 4


# --- graph output ---


def _graph_flow():
    return Flow(
        "my flow",
        [
            {"id": "a", "processor": "echo"},
            {"id": "b", "processor": "echo", "depends_on": "a"},
            {"id": 'say "hi"', "processor": "echo", "depends_on": "a"},
        ],
    )


def test_to_mermaid():
    text = _graph_flow().to_mermaid()
    assert text.splitlines() == [
        "flowchart LR",
        '    n0["a<br/>(echo)"]',
        '    n1["b<br/>(echo)"]',
        '    n2["say #quot;hi#quot;<br/>(echo)"]',
        "    n0 --> n1",
        "    n0 --> n2",
    ]
    assert _graph_flow().to_mermaid("TB").startswith("flowchart TB\n")


def test_to_dot():
    text = _graph_flow().to_dot()
    assert text.startswith('digraph "my flow" {\n    rankdir=LR;\n')
    assert '    "a" [label="a\\necho"];' in text
    assert '    "say \\"hi\\"" [label="say \\"hi\\"\\necho"];' in text
    assert '    "a" -> "say \\"hi\\"";' in text
    assert text.endswith("}\n")


def test_graph_unknown_step_raises():
    flow = Flow("t", [{"id": "a", "processor": "echo", "depends_on": "x"}])
    with pytest.raises(FlowError):
        flow.to_mermaid()
    with pytest.raises(FlowError):
        flow.to_dot()


# --- read_file ---


def test_read_file_formats(tmp_path):
    (tmp_path / "a.txt").write_text("one\ntwo\n")
    (tmp_path / "a.json").write_text('{"n": 1}')
    (tmp_path / "a.toml").write_text("n = 2\n")
    result = Flow(
        "t",
        [
            {
                "id": "text",
                "processor": "read_file",
                "config": {"path": str(tmp_path / "a.txt")},
            },
            {
                "id": "lines",
                "processor": "read_file",
                "config": {"path": str(tmp_path / "a.txt"), "format": "lines"},
            },
            {
                "id": "json",
                "processor": "read_file",
                "config": {"path": str(tmp_path / "a.json")},
            },
            {
                "id": "toml",
                "processor": "read_file",
                "config": {"path": str(tmp_path / "a.toml")},
            },
            {
                "id": "raw",
                "processor": "read_file",
                "config": {"path": str(tmp_path / "a.json"), "format": "text"},
            },
        ],
    ).run()
    assert result.status == "success", [s.error for s in result.steps]
    assert result.get("text").output == {
        "path": str((tmp_path / "a.txt").resolve()),
        "size": 8,
        "text": "one\ntwo\n",
        "data": None,
    }
    assert result.get("lines").output["data"] == ["one", "two"]
    assert result.get("json").output["data"] == {"n": 1}
    assert result.get("toml").output["data"] == {"n": 2}
    assert result.get("raw").output["data"] is None


def test_read_file_path_reference_and_errors(tmp_path):
    (tmp_path / "big.txt").write_text("x" * 100)
    result = Flow(
        "t",
        [
            {
                "id": "a",
                "processor": "read_file",
                "config": {"path": "${input}/big.txt", "max_size": 10},
            },
            {
                "id": "b",
                "processor": "read_file",
                "config": {"path": "${input}/missing.txt"},
            },
        ],
    ).run(input_data=str(tmp_path))
    assert "more than max_size 10" in result.get("a").error
    assert result.get("b").status == "skipped"

    result = Flow(
        "t",
        [
            {
                "id": "b",
                "processor": "read_file",
                "config": {"path": str(tmp_path / "missing.txt")},
            }
        ],
    ).run()
    assert result.get("b").error.startswith("FileNotFoundError")
