from collections.abc import Generator
from typing import Any

import pydantic

from geenii.flow.flow import FlowContext, FlowProcessor, StepEvent, register_processor


class EchoConfig(pydantic.BaseModel):
    message: Any = None


class EchoOutput(pydantic.BaseModel):
    message: Any


@register_processor("echo")
class EchoProcessor(FlowProcessor):
    """Returns the configured message, or the step input if no message is set"""

    config_model = EchoConfig
    output_model = EchoOutput

    def process(
        self, input_data: Any, ctx: FlowContext
    ) -> Generator[Any, None, EchoOutput]:
        message = input_data if self.config.message is None else self.config.message
        yield StepEvent("log", message)
        return EchoOutput(message=message)
