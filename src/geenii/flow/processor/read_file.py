import json
import tomllib
from collections.abc import Generator
from pathlib import Path
from typing import Any, Literal

import pydantic

from geenii.flow.flow import FlowContext, FlowProcessor, StepEvent, register_processor

FORMAT_BY_SUFFIX = {".json": "json", ".toml": "toml"}


class ReadFileConfig(pydantic.BaseModel):
    path: str
    format: Literal["auto", "text", "json", "toml", "lines"] = "auto"
    encoding: str = "utf-8"
    max_size: int | None = None


class ReadFileOutput(pydantic.BaseModel):
    path: str
    size: int
    text: str
    data: Any = None


@register_processor("read_file")
class ReadFileProcessor(FlowProcessor):
    """Reads a text file. JSON, TOML or lines are parsed into `data`; format "auto" picks by file extension."""

    config_model = ReadFileConfig
    output_model = ReadFileOutput

    def process(self, input_data: Any, ctx: FlowContext) -> Generator[Any, None, ReadFileOutput]:
        c: ReadFileConfig = self.config
        path = Path(c.path).expanduser().resolve()
        size = path.stat().st_size
        if c.max_size is not None and size > c.max_size:
            raise ValueError(f"{path} is {size} bytes, more than max_size {c.max_size}")
        yield StepEvent("log", f"Reading {path} ({size} bytes)")

        text = path.read_text(encoding=c.encoding)
        fmt = FORMAT_BY_SUFFIX.get(path.suffix.lower(), "text") if c.format == "auto" else c.format
        if fmt == "json":
            data = json.loads(text)
        elif fmt == "toml":
            data = tomllib.loads(text)
        elif fmt == "lines":
            data = text.splitlines()
        else:
            data = None
        return ReadFileOutput(path=str(path), size=size, text=text, data=data)
