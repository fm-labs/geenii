"""Unattended agent instances.

`geenii worker serve <agent>` runs one instance: it takes messages from the agent's inbox one at a time, answers each
with a fresh agent (no memory carried between messages), and mails the answer back to the sender. Several
instances of the same agent can share one inbox: taking a message is an atomic rename, so each message is
handled at most once.

A message being worked on sits in inbox/<agent>/processing/<instance>/ and moves to read/ once it is answered.
If the instance dies first, another instance of the agent finds the message (see `recover`), moves it to
failed/ and tells the sender; it is never handled a second time.

Safety rules:
- Every tool call follows an approval policy, since nobody is there to ask: "none" (default) denies all tool
  calls, "all" approves all, and "tool1,tool2" approves only the listed tools.
- A message that is itself a reply (has `reply_to`) is processed but never auto-answered, so two agents can't
  get stuck answering each other's answers.

Each instance writes a heartbeat to GEENII_HOME/workers/<agent>/<instance>.json (see `geenii worker list`).
"""

from __future__ import annotations

import json
import os
import signal
import socket
import threading
import time
from datetime import UTC, datetime

from geenii.agent.registry import AgentSpec
from geenii.chat_models import JsonContent, TextContent
from geenii.config import geenii_home
from geenii.datamodels import ModelMessage, SystemMessage
from geenii.g import init_agent
from geenii.hitl import HumanInTheLoopController, PolicyHumanInTheLoopController
from geenii.memory import ShortTermChatMemory

from geenii.ibc.comms import MAX_SUBJECT, MAX_TEXT, Mailbox, known_agents

HEARTBEAT_SECONDS = 15  # how often a running worker refreshes its heartbeat file, also while busy
STALE_SECONDS = 4 * HEARTBEAT_SECONDS  # a worker not seen for this long is probably gone


def instance_id() -> str:
    return f"{socket.gethostname()}-{os.getpid()}"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def log(event: str, **fields) -> None:
    print(json.dumps({"ts": _now(), "event": event, **fields}, ensure_ascii=False), flush=True)


def instance_alive(agent: str, instance: str, stale_seconds: float = STALE_SECONDS) -> bool:
    """Whether the worker INSTANCE of AGENT still runs, judged by its heartbeat file (and its pid on this host)."""
    path = geenii_home() / "workers" / agent / f"{instance}.json"
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        age = (datetime.now(UTC) - datetime.fromisoformat(state["last_seen"])).total_seconds()
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return False  # no (readable) heartbeat: a worker removes it only when it holds no messages
    if age > stale_seconds:
        return False
    host, _, pid = instance.rpartition("-")
    if host == socket.gethostname() and pid.isdigit():
        try:
            os.kill(int(pid), 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            pass  # exists, owned by someone else
    return True


def recover(spec: AgentSpec, instance: str, *, include_self: bool = False) -> list[tuple[str, dict, bool]]:
    """Take over the messages that dead instances of the agent were working on.

    A message that was already answered moves to read/. Every other one moves to failed/ and the sender is
    told that it wasn't answered; it is not handled again. With include_self, messages held under this
    instance's own id are taken too (at startup they can only come from an earlier process with the same id).
    """

    def is_alive(owner: str) -> bool:
        if owner == instance:
            return not include_self
        return instance_alive(spec.name, owner)

    def was_answered(message: dict) -> bool:
        try:
            return Mailbox(message["from"]).find_reply(message["id"]) is not None
        except (KeyError, ValueError):
            return False

    recovered = Mailbox(spec.name).recover(is_alive, was_answered)
    for owner, message, answered in recovered:
        notified = False
        if not answered:
            try:
                notified = reply(spec, message, f"Your message could not be answered: the worker handling it "
                                                f"({owner}) stopped unexpectedly. It will not be retried.")
            except Exception:
                pass
        log("message.recovered", agent=spec.name, instance=instance, id=message.get("id"), owner=owner,
            answered=answered, notified=notified)
    return recovered


def final_answer(messages: list) -> str:
    """The text to send back: the agent's last JSON or text answer, or an error that came after it.

    Info and warning system messages (status notes) are never the answer; an error system message is, but
    only when no answer follows it, since then the run failed.
    """
    for msg in reversed(messages):
        if isinstance(msg, ModelMessage) and msg.role == "assistant":
            json_parts = [p.data for p in msg.content if isinstance(p, JsonContent)]
            if json_parts:
                return json.dumps(json_parts[0], ensure_ascii=False, indent=2)
            text = "\n".join(p.text for p in msg.content if isinstance(p, TextContent)).strip()
            if text:
                return text
        elif isinstance(msg, SystemMessage) and msg.level == "error":
            text = msg.to_text().strip()
            if text:
                return f"Error: {text}"
    return "(no answer)"


def handle(spec: AgentSpec, message: dict, model: str | None, hitl: HumanInTheLoopController) -> str:
    agent = init_agent(spec, model=model, memory=ShortTermChatMemory(), hitl=hitl)
    #if spec.task_factory is not None:
    #    prompt = message["body"]  # recommenders take the task as-is
    #else:
    prompt = f"Message from agent '{message['from']}' (subject: {message['subject']}):\n\n{message['body']}"
    return final_answer(list(agent.process(prompt)))


def reply(spec: AgentSpec, message: dict, answer: str) -> bool:
    """Mail `answer` back to the sender; False if the message must not be answered (see the safety rules)."""
    sender = message.get("from")
    if message.get("reply_to") is not None or sender == spec.name or sender not in known_agents():
        return False
    answer = (answer or "").strip() or "(no answer)"  # Mailbox.send rejects an empty body
    if len(answer) > MAX_TEXT:
        answer = answer[: MAX_TEXT - 20] + "\n... [truncated]"
    subject = f"Re: {message.get('subject') or ''}".strip()[:MAX_SUBJECT]
    Mailbox.send(spec.name, sender, subject, answer, reply_to=message["id"])
    return True


class Heartbeat:
    """The worker's status file. A background thread refreshes it every `interval` seconds, so a worker that is
    busy with one long message still shows as alive."""

    def __init__(self, agent: str, instance: str, interval: float = HEARTBEAT_SECONDS):
        self.path = geenii_home() / "workers" / agent / f"{instance}.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.state = {"agent": agent, "instance": instance, "pid": os.getpid(), "started": _now(), "handled": 0,
                      "status": "starting"}
        self.interval = interval
        self._lock = threading.Lock()  # the main loop and the background thread both write the file
        self._stopped = threading.Event()
        self._thread: threading.Thread | None = None

    def beat(self, **changes) -> None:
        with self._lock:
            self.state.update(changes, last_seen=_now())
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.state), encoding="utf-8")
            os.replace(tmp, self.path)

    def start(self) -> None:
        self.beat()
        self._thread = threading.Thread(target=self._run, name="worker-heartbeat", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stopped.wait(self.interval):
            try:
                self.beat()
            except OSError:
                pass  # a missed beat is harmless; the next one tries again

    def remove(self) -> None:
        self._stopped.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        with self._lock:
            self.path.unlink(missing_ok=True)


def serve(spec: AgentSpec, model: str | None = None, *, poll_seconds: float = 2.0, once: bool = False,
          approval_policy: str = "none") -> int:
    """Work through the inbox until stopped (SIGTERM/SIGINT); with once=True, stop when the inbox is empty."""
    instance = instance_id()
    approver = PolicyHumanInTheLoopController.from_policy(approval_policy)
    mailbox = Mailbox(spec.name)
    heartbeat = Heartbeat(spec.name, instance)
    stopping = False

    def stop(signum, frame):
        nonlocal stopping
        stopping = True

    previous = {sig: signal.signal(sig, stop) for sig in (signal.SIGTERM, signal.SIGINT)}
    log("worker.start", agent=spec.name, instance=instance, model=model or "default", approval=approver.describe())
    try:
        heartbeat.start()
        recover(spec, instance, include_self=True)
        last_recover = time.monotonic()
        while not stopping:
            heartbeat.beat(status="idle")
            if time.monotonic() - last_recover >= HEARTBEAT_SECONDS:
                recover(spec, instance)
                last_recover = time.monotonic()
            message = mailbox.claim_next(owner=instance)
            if message is None:
                if once:
                    break
                time.sleep(poll_seconds)
                continue
            heartbeat.beat(status="busy", message_id=message["id"], busy_since=_now())
            log("message.start", agent=spec.name, instance=instance, id=message["id"], sender=message["from"],
                subject=message["subject"])
            started = time.monotonic()
            try:
                answer, ok = handle(spec, message, model, approver), True
            except Exception as e:  # one bad message must not stop the worker
                answer, ok = f"Error while handling your message: {e}", False
            seconds = round(time.monotonic() - started, 1)
            try:
                replied = reply(spec, message, answer)
                finish = mailbox.ack  # done: read/
            except Exception as e:  # a failed reply must not stop the worker either
                replied = False
                log("message.reply_failed", agent=spec.name, instance=instance, id=message["id"], error=str(e))
                finish = mailbox.fail  # not answered: failed/
            try:
                finish(message["id"], instance)
            except OSError as e:  # stays in processing/; recovered once this instance is gone
                log("message.finish_failed", agent=spec.name, instance=instance, id=message["id"], error=str(e))
            heartbeat.beat(handled=heartbeat.state["handled"] + 1, message_id=None, busy_since=None)
            log("message.done", agent=spec.name, instance=instance, id=message["id"], ok=ok, seconds=seconds, replied=replied)
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        heartbeat.remove()
        log("worker.stop", agent=spec.name, instance=instance, handled=heartbeat.state["handled"])
    return 0


def list_workers(stale_seconds: float = STALE_SECONDS) -> list[dict]:
    folder = geenii_home() / "workers"
    workers = []
    for path in sorted(folder.glob("*/*.json")) if folder.is_dir() else []:
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            age = (datetime.now(UTC) - datetime.fromisoformat(state["last_seen"])).total_seconds()
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue  # unreadable or damaged heartbeat file
        state["seconds_since_seen"] = round(age)
        state["alive"] = age <= stale_seconds
        workers.append(state)
    return workers


def ask(agent: str, text: str, *, sender: str = "human", subject: str | None = None, timeout: float = 300,
        poll_seconds: float = 1.0) -> dict | None:
    """Mail `text` to `agent` and wait for the reply (needs a running `geenii worker serve <agent>`)."""
    sent = Mailbox.send(sender, agent, subject or text.splitlines()[0][:80], text)
    inbox = Mailbox(sender)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for header in inbox.list():
            if header.get("reply_to") == sent["id"]:
                return inbox.read(header["id"])
        time.sleep(poll_seconds)
    return None
