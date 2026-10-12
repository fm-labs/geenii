from typing import Any, Generator

import pydantic

from geenii.flow.flow import FlowContext, FlowStep, StepEvent, register_step


class EchoConfig(pydantic.BaseModel):
    message: Any = None


class EchoOutput(pydantic.BaseModel):
    message: Any


@register_step("echo")
class EchoStep(FlowStep):
    """Returns the configured message, or the step input if no message is set"""

    config_model = EchoConfig
    output_model = EchoOutput

    def process(self, input_data: Any, ctx: FlowContext) -> Generator[Any, None, EchoOutput]:
        message = input_data if self.config.message is None else self.config.message
        yield StepEvent("log", message)
        return EchoOutput(message=message)
