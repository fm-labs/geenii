import time
from typing import Any, Generator

import pydantic

from geenii.flow.flow import FlowContext, FlowProcessor, StepEvent, register_processor
from geenii.pm.process_manager_client import ProcessManagerClient

# Bytes per output request while following a process
CHUNK_SIZE = 64 * 1024
# A chunk read from the process manager can be up to 3 bytes shorter than the limit
# (a UTF-8 character split at its start belongs to the previous chunk)
_UTF8_MAX_CONT = 3

_FINISHED_STATES = ("completed", "failed", "killed", "orphaned")


class ExecutePmCommandConfig(pydantic.BaseModel):
    command: str | list[str] = pydantic.Field(
        ..., description="A string runs through the shell; a list is executed directly"
    )
    cwd: str | None = None
    env: dict[str, str] | None = None
    pid: str | None = pydantic.Field(
        None, description="Custom process ID (auto-generated if omitted)"
    )
    wait: bool = pydantic.Field(
        True,
        description="Wait for the process to finish, streaming its output; "
        "otherwise return right after starting it",
    )
    timeout: float | None = pydantic.Field(
        None,
        description="With wait: kill the process and fail the step after this many seconds",
    )
    check: bool = pydantic.Field(
        False,
        description="With wait: fail the step unless the process completed (rc 0)",
    )
    poll_interval: float = pydantic.Field(
        0.5, gt=0, description="Seconds between output polls while waiting"
    )
    socket: str | None = pydantic.Field(
        None, description="Daemon socket path (default: GEENII_SOCKET or the cache dir)"
    )


class ExecutePmCommandOutput(pydantic.BaseModel):
    process_id: str
    system_pid: int
    state: str
    rc: int | None = None
    stdout: str | None = None
    stderr: str | None = None


class _OutputFollower:
    """
    Follows one output stream of a process-manager process, returning complete lines.

    Reads CHUNK_SIZE-byte chunks via offset/limit. A chunk is complete once the chunk
    after it exists; the last chunk is re-read on each poll and only consumed up to
    its last newline, so a line still being written is never split.
    """

    def __init__(
        self,
        client: ProcessManagerClient,
        process_id: str,
        stream: str,
        chunk_size: int | None = None,
    ):
        self.client = client
        self.process_id = process_id
        self.stream = stream
        self.chunk_size = chunk_size or CHUNK_SIZE
        self.offset = 0  # byte offset of the current chunk
        self.seen = 0  # characters of the current chunk already consumed
        self.partial = ""  # an incomplete line carried over from a completed chunk
        self.parts: list[str] = []

    @property
    def text(self) -> str:
        return "".join(self.parts)

    def _read(self, offset: int) -> str:
        return self.client.output(
            self.process_id, stream=self.stream, offset=offset, limit=self.chunk_size
        )

    def poll(self, final: bool = False) -> list[str]:
        """Return the lines written since the last poll. final: the process has exited, flush everything."""
        lines: list[str] = []
        text = self._read(self.offset)
        while len(text.encode()) >= self.chunk_size - _UTF8_MAX_CONT:
            # Possibly a full chunk: it is complete if the next one exists
            following = self._read(self.offset + self.chunk_size)
            if not following:
                break
            self._consume(text[self.seen :], lines)
            self.offset += self.chunk_size
            self.seen = 0
            text = following

        new = text[self.seen :]
        if not final:
            new = new[: new.rfind("\n") + 1]
        self.seen += len(new)
        self._consume(new, lines)
        if final and self.partial:
            lines.append(self.partial.rstrip("\r"))
            self.partial = ""
        return lines

    def _consume(self, s: str, lines: list[str]):
        if not s:
            return
        self.parts.append(s)
        *complete, self.partial = (self.partial + s).split("\n")
        lines.extend(line.rstrip("\r") for line in complete)


@register_processor("execute_pm_command")
class ExecutePmCommandProcessor(FlowProcessor):
    """Starts a background process via the geenii daemon's process manager, optionally waiting for it"""

    config_model = ExecutePmCommandConfig
    output_model = ExecutePmCommandOutput

    def process(
        self, input_data: Any, ctx: FlowContext
    ) -> Generator[Any, None, ExecutePmCommandOutput]:
        c: ExecutePmCommandConfig = self.config
        client = ProcessManagerClient(c.socket)
        info = client.start(c.command, env=c.env, cwd=c.cwd, pid=c.pid)
        process_id = info["pid"]
        yield StepEvent(
            "log",
            f"Started process {process_id} (system pid {info['system_pid']}): {c.command!r}",
        )
        if not c.wait:
            return ExecutePmCommandOutput(
                process_id=process_id,
                system_pid=info["system_pid"],
                state=info["state"],
            )

        followers = [
            _OutputFollower(client, process_id, s) for s in ("stdout", "stderr")
        ]
        deadline = time.monotonic() + c.timeout if c.timeout is not None else None
        try:
            while True:
                info = client.status(process_id)
                finished = info["state"] in _FINISHED_STATES
                # Read after the status check: once finished, the logs are complete
                for f in followers:
                    for line in f.poll(final=finished):
                        yield StepEvent(f.stream, line)
                if finished:
                    break
                if ctx.stopping:
                    raise RuntimeError(f"Flow is stopping; killed process {process_id}")
                if deadline is not None and time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"Process {process_id} did not finish within {c.timeout}s; killed it"
                    )
                time.sleep(c.poll_interval)
        except BaseException:
            # The step owns the process while waiting: don't leave it running
            try:
                client.kill(process_id)
            except Exception:
                pass
            raise

        output = ExecutePmCommandOutput(
            process_id=process_id,
            system_pid=info["system_pid"],
            state=info["state"],
            rc=info.get("exit_code"),
            stdout=followers[0].text,
            stderr=followers[1].text,
        )
        if c.check and output.state != "completed":
            raise RuntimeError(
                f"Process {process_id} {output.state} with exit code {output.rc}: "
                f"{output.stderr.strip()[-500:]}"
            )
        return output
