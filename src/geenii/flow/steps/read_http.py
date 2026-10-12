from typing import Any, ClassVar, Generator

import httpx
import pydantic

from geenii.flow.flow import FlowContext, FlowStep, StepEvent, register_step


class ReadHttpConfig(pydantic.BaseModel):
    url: str
    method: str = "GET"
    headers: dict[str, str] = {}
    params: dict[str, Any] = {}
    body: Any = None
    timeout: float = 30.0
    raise_for_status: bool = True


class ReadHttpOutput(pydantic.BaseModel):
    status: int
    headers: dict[str, str]
    text: str
    data: Any = None


@register_step("read_http")
class ReadHttpStep(FlowStep):
    """Sends an HTTP request. `body` is sent as JSON; a JSON response is parsed into `data`."""

    config_model = ReadHttpConfig
    output_model = ReadHttpOutput

    # override in tests, e.g. with httpx.MockTransport
    transport: ClassVar[httpx.BaseTransport | None] = None

    def process(self, input_data: Any, ctx: FlowContext) -> Generator[Any, None, ReadHttpOutput]:
        c: ReadHttpConfig = self.config
        yield StepEvent("log", f"{c.method} {c.url}")
        with httpx.Client(timeout=c.timeout, transport=self.transport) as client:
            resp = client.request(c.method, c.url, headers=c.headers, params=c.params,
                                  json=c.body if c.body is not None else None)
        if c.raise_for_status:
            resp.raise_for_status()
        data = None
        if "json" in resp.headers.get("content-type", ""):
            data = resp.json()
        return ReadHttpOutput(status=resp.status_code, headers=dict(resp.headers), text=resp.text, data=data)
