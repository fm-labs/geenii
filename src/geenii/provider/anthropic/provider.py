import anthropic
import json
import logging
import time
import uuid
from typing import List

from geenii import config
from geenii.chat_models import TextContent, ToolCallContent, ContentPart, ToolCallResultContent, JsonContent
from geenii.datamodels import ChatCompletionResponse, ChatCompletionRequest, AIModelInfo, ModelMessage
from geenii.provider.interfaces import AIProvider, AIChatCompletionProvider

logger = logging.getLogger(__name__)

KNOWN_MODELS = [
    "claude-fable-5",
    "claude-sonnet-5",
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-haiku-4-5",
]


class AnthropicAIProvider(AIProvider, AIChatCompletionProvider):
    DEFAULT_MODEL = "claude-opus-4-6"
    DEFAULT_TEMPERATURE = 0.2
    DEFAULT_MAX_TOKENS = 4096

    def __init__(self, **kwargs):
        super().__init__(name="anthropic")
        self._client = None

    @property
    def client(self) -> anthropic.Anthropic:
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        return self._client

    def is_configured(self) -> bool:
        return bool(config.ANTHROPIC_API_KEY)

    def get_capabilities(self) -> list[str]:
        return ["chat_completion", "tool_calling"]

    def get_models(self) -> list[AIModelInfo]:
        models = []
        for model_name in KNOWN_MODELS:
            models.append(AIModelInfo(
                provider=self.name,
                name=model_name,
                locality="cloud",
                description=f"Anthropic model {model_name}",
                capabilities=["chat_completion", "tool_calling"],
                installed=True,
            ))
        return models

    def generate_chat_completion(self, request: ChatCompletionRequest, tool_registry=None) -> ChatCompletionResponse:
        model = request.model or self.DEFAULT_MODEL
        if model.startswith("anthropic:"):
            model = model[len("anthropic:"):]

        # TOOLS
        tools = request.tools or set()
        anthropic_tools = []
        if tool_registry is not None and len(tools) > 0:
            tool_defs = tool_registry.list_definitions()
            matching = [td for td in tool_defs if td["name"] in tools]
            anthropic_tools = [_to_anthropic_tool(td) for td in matching]
            logger.info(f"Mapped {len(anthropic_tools)} tools to Anthropic format")

        # SYSTEM PROMPT — pass as list of text blocks so the API can cache static parts
        system_blocks = _build_system_blocks(request.system) if request.system else []

        # MESSAGES
        input_messages = []
        if request.messages:
            input_messages.extend(_model_messages_to_anthropic_format(request.messages))
        if request.prompt:
            input_messages.append({"role": "user", "content": request.prompt})
        elif not input_messages:
            raise ValueError("At least a prompt or some messages must be provided for chat completion.")

        # OUTPUT
        output_format = request.output_format
        output_schema = request.output_schema

        output_config = {}
        if output_schema is not None:
            output_config["format"] = {"schema": output_schema, "type": "json_schema"}
        elif output_format == "json" and output_schema is None:
            output_schema = {
                "type": "object",
                "properties": {
                    "result": {"type": "string"},
                },
                "additionalProperties": True,
            }
            output_config["format"] = {"schema": output_schema, "type": "json_schema"}


        model_params = request.model_parameters or {}
        temperature = model_params.get("temperature", request.temperature) or self.DEFAULT_TEMPERATURE
        max_tokens = model_params.get("max_tokens", request.max_tokens) or self.DEFAULT_MAX_TOKENS

        try:
            logger.info(f"ANTHROPIC: Generating chat completion model={model} with {len(input_messages)} input messages")

            create_kwargs = dict(
                model=model,
                messages=input_messages,
                max_tokens=max_tokens,
                temperature=temperature,
                output_config=output_config,
            )
            print(create_kwargs)

            if system_blocks:
                create_kwargs["system"] = system_blocks
            if anthropic_tools:
                create_kwargs["tools"] = anthropic_tools

            model_result = self.client.messages.create(**create_kwargs)

            output_parts: List[ContentPart] = []

            for block in model_result.content:
                if block.type == "text":
                    text = block.text
                    _out_part = TextContent(text=text)
                    if output_format == "json":
                        try:
                            _out_part = JsonContent(data=json.loads(text))
                        except json.JSONDecodeError:
                            logger.warning("Failed to parse content as JSON, adding as plain text.")
                    elif output_format is None or output_format == "auto":
                        if isinstance(text, str) and text.strip().startswith("{") and text.strip().endswith("}"):
                            try:
                                _out_part = JsonContent(data=json.loads(text))
                            except json.JSONDecodeError:
                                pass
                    output_parts.append(_out_part)

                elif block.type == "tool_use":
                    output_parts.append(ToolCallContent(
                        name=block.name,
                        arguments=block.input or {},
                        call_id=block.id,
                    ))
                    logger.info(f"Tool call requested: {block.name} with call_id {block.id}")

            cache_creation = getattr(model_result.usage, "cache_creation_input_tokens", 0) or 0
            cache_read = getattr(model_result.usage, "cache_read_input_tokens", 0) or 0
            usage = {
                "input_tokens": model_result.usage.input_tokens,
                "output_tokens": model_result.usage.output_tokens,
                "total_tokens": model_result.usage.input_tokens + model_result.usage.output_tokens,
                "cache_creation_input_tokens": cache_creation,
                "cache_read_input_tokens": cache_read,
            }
            logger.info(f"Tokens used: {usage['total_tokens']} (cache write: {cache_creation}, cache read: {cache_read})")

            response = ChatCompletionResponse(
                id=model_result.id,
                timestamp=int(time.time()),
                model=f"{self.name}:{model}",
                prompt=request.prompt,
                output=output_parts,
                model_result=model_result.model_dump(),
                usage=usage,
            )
            return response

        except Exception as e:
            logger.error("ANTHROPIC: Error generating chat completion: %s", str(e))
            raise


def _build_system_blocks(system_parts: list[str]) -> list[dict]:
    """Convert system prompt parts to Anthropic text blocks with cache_control on the first (static) block."""
    blocks = []
    for i, text in enumerate(system_parts):
        if not text:
            continue
        block = {"type": "text", "text": text}
        if i == 0:
            block["cache_control"] = {"type": "ephemeral"}
        blocks.append(block)
    return blocks


def _to_anthropic_tool(tool_def: dict) -> dict:
    return {
        "name": tool_def["name"],
        "description": tool_def.get("description", ""),
        "input_schema": tool_def.get("parameters", {"type": "object", "properties": {}}),
    }


def _model_messages_to_anthropic_format(messages: List[ModelMessage]) -> List[dict]:
    anthropic_messages = []
    for message in messages:
        role = message.role
        if role == "system":
            continue

        for content_item in message.content:
            if isinstance(content_item, TextContent):
                anthropic_messages.append({
                    "role": role,
                    "content": content_item.text,
                })
            elif isinstance(content_item, JsonContent):
                anthropic_messages.append({
                    "role": role,
                    "content": json.dumps(content_item.data),
                })
            elif isinstance(content_item, ToolCallContent):
                anthropic_messages.append({
                    "role": "assistant",
                    "content": [{
                        "type": "tool_use",
                        "id": content_item.call_id or ("call_" + uuid.uuid4().hex),
                        "name": content_item.name,
                        "input": content_item.arguments or {},
                    }],
                })
            elif isinstance(content_item, ToolCallResultContent):
                anthropic_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": content_item.call_id or "",
                        "content": str(content_item.result) if content_item.result is not None else "",
                    }],
                })
            else:
                anthropic_messages.append({
                    "role": role,
                    "content": content_item.to_text(),
                })
    return anthropic_messages


ai_provider_class = AnthropicAIProvider
