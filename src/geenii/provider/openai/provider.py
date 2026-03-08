import json
import os
import time
import uuid
import datetime
import logging

from openai import OpenAI

from geenii import config
from geenii.chat.chat_models import TextContent, ToolCallContent, JsonContent
from geenii.config import CACHE_DIR
from geenii.datamodels import CompletionResponse, ImageGenerationApiResponse, ChatCompletionRequest, \
    ChatCompletionResponse, AIModelInfo, AudioTranscriptionApiResponse
from geenii.provider.interfaces import AIProvider, AICompletionProvider, AIChatCompletionProvider, \
    AIImageGeneratorProvider, AIAudioTranscriptionProvider
from geenii.tool.registry import ToolRegistry
from geenii.utils.json_util import write_json

logger = logging.getLogger(__name__)

class OpenAIProvider(AIProvider, AICompletionProvider, AIChatCompletionProvider, AIImageGeneratorProvider,
                     AIAudioTranscriptionProvider):
    """
    A class to represent the OpenAI provider for XAI.
    """

    DEFAULT_MODEL = "gpt-3.5-turbo"
    DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant, that gives short and concise answers. Always use the tools if you can. If you don't know the answer, say you don't know and don't try to make up an answer. Always use the tools if you can. If you don't know the answer, say you don't know and don't try to make up an answer."

    DEFAULT_TEMPERATURE = 0.3
    DEFAULT_MAX_TOKENS = 4096
    DEFAULT_MAX_TOOL_CALLS = 5

    DALLE_MODELS = {
        "gpt-image-1": {"sizes": ["1024x1024", "auto"]},
        "dall-e-2": {"sizes": ["256x256", "512x512", "1024x1024"]},
        "dall-e-3": {"sizes": ["1024x1024", "1792x1024", "1024x1792"]}
    }

    TRANSCRIPTION_MODELS = {
        "whisper-1": {},
        "gpt-4o-transcribe": {},
        "gpt-4o-mini-transcribe": {},
        "gpt-4o-transcribe-diarize": {},
    }

    def __init__(self, **kwargs):
        super().__init__(name="openai")
        self._client = None

    @property
    def client(self):
        if self._client is None:
            api_key = os.environ.get("OPENAI_API_KEY", None)
            if not api_key:
                raise ValueError("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")

            print(f"Connecting using OpenAI API Key starting with '{config.OPENAI_API_KEY[:13]}..'")
            return OpenAI(api_key=config.OPENAI_API_KEY)
        return self._client

    def is_configured(self) -> bool:
        return config.OPENAI_API_KEY is not None and len(config.OPENAI_API_KEY) > 0

    def get_capabilities(self) -> list[str]:
        return ['completion', 'chat_completion', 'tool_calling', 'image_generation']

    def get_models(self) -> list[AIModelInfo]:
        models = []

        def datetime_from_timestamp(ts):
            """Convert a Unix timestamp to a human-readable datetime isoformat."""
            return datetime.datetime.fromtimestamp(ts).isoformat()

        try:
            openai_models = self.client.models.list()

            cache_data = {"models": [model.model_dump(mode="json") for model in openai_models.data]}
            write_json(f"{CACHE_DIR}/openai.models.json", cache_data)
        except Exception as e:
            print(f"Error fetching models from OpenAI: {e}")
            return models

        # print(openai_models)
        # Example Entry: Model(id='gpt-4-0613', created=1686588896, object='model', owned_by='openai')
        for model in openai_models.data:
            # filter out models that are not relevant for completion or chat (e.g. audio, image, fine-tuning models)
            #if not any(keyword in model.id for keyword in ["gpt", "davinci", "curie", "babbage", "ada"]):
            if not any(keyword in model.id for keyword in ["gpt"]):
                continue

            # filter out preview models and models with date-suffixes (e.g. gpt-4-2024-08-06)
            if any(keyword in model.id for keyword in ["preview", "2024-", "2025-", "2026-", "image", "audio", "tts", "codex"]):
                continue

            models.append(AIModelInfo(
                provider=self.name,
                name=model.id,
                locality="cloud",
                description=f"OpenAI model {model.id}",
                capabilities=[],  # self.get_capabilities(),
                metadata={
                    "created_at": datetime_from_timestamp(model.created),
                    "owned_by": model.owned_by,
                    "object": model.object
                }
            ))
        return models

    def generate_completion(self, prompt: str, model: str = DEFAULT_MODEL, **kwargs) -> CompletionResponse:
        """
        Get openai completion for the given prompt via OpenAI Responses API.

        :param prompt: The prompt string to generate a completion for.
        :param model: The model to use for the completion (default is 'gpt-3.5-turbo').
        :param kwargs: The keyword arguments for the OpenAI API request.
            Supported kwargs include:
                - system: Optional system instructions to include in the prompt.
                - stream: Whether to stream the response (default is False).
                - temperature: The sampling temperature to use (default is 0.5).
                - max_tokens: The maximum number of tokens to generate (default is 4096).
                - top_p: The nucleus sampling probability to use (optional).
                - output_format: The format of the output, either 'json' or a JSON schema object (optional).
        :return:
        """

        system = kwargs.get('system', None)
        stream = kwargs.get('stream', False)
        temperature = kwargs.get('temperature', 0.5)
        max_tokens = kwargs.get('max_tokens', 4096)
        top_p = kwargs.get('top_p', None)
        # top_k = kwargs.get('top_k', None) # top_k is not supported in OpenAI Responses API
        output_format = kwargs.get('output_format', None)
        if isinstance(output_format, str):
            if output_format.lower() == "json" or output_format.lower() == "json_object":
                output_format = {"type": "json_object"}
            else:
                raise ValueError(
                    f"Unsupported format: {output_format}. Supported formats are: 'json' or pass a JSON schema object.")
        # if not isinstance(format, dict):
        #    raise ValueError(f"Format must be a string or a JSON schema object, got {type(format)}.")

        # if model not in self.get_models():
        #    raise ValueError(f"Model {model} is not supported by {repr(self)}.")

        input_messages = kwargs.get('input', [])
        # if system is not None:
        #    input_messages.append({"role": "system", "content": system})
        input_messages.append({"role": "user", "content": prompt})

        model_result = self.client.responses.create(
            model=model,
            instructions=system,
            input=input_messages,
            stream=stream,
            temperature=temperature,
            max_output_tokens=max_tokens,
            text=output_format,
            top_p=top_p,
        )

        output = [item.model_dump() for item in model_result.output]
        response = CompletionResponse(
            id=uuid.uuid4().hex,
            timestamp=int(time.time()),
            # prompt=prompt,
            model=model,
            # provider=self.name,
            # the output from the model response in OpenAI Responses API format
            output=output,
            # the aggregated text output from all output_text items in the output array
            output_text=model_result.output_text,
            # the full model result for debugging
            model_result=model_result.model_dump()
        )
        return response

    def generate_chat_completion(self, request: ChatCompletionRequest, tool_registry: ToolRegistry=None) -> ChatCompletionResponse:
        model = request.model or self.DEFAULT_MODEL
        if model.startswith("openai:"):
            model = model[len("openai:"):]

        # map tool names to tool definitions in openai format
        tools = request.tools or set()
        tool_defs_openai = []
        logger.info(f"Tool registry provided {tool_registry is not None}, tools requested: {tools}")
        if tool_registry is not None and len(tools) > 0:
            _tools = tool_registry.list_tools()
            tool_defs_openai = [_tool.to_openai() for _tool in _tools if _tool.name in tools]
            logger.info(f"OpenAI tools mapped: {len(tool_defs_openai)}")

        # mapping history/seed model messages to OpenAI Responses API input format
        messages = request.messages or []
        input_messages = []
        for message in messages:
            if message.content and len(message.content) > 0:
                for content_item in message.content:
                    if content_item.type == "text":
                        input_messages.append({"role": message.role, "content": content_item.text})
                    elif content_item.type == "tool_call":
                        input_messages.append({
                            "type": "function_call",
                            "call_id": content_item.call_id,
                            "name": content_item.name,
                            "arguments": json.dumps(content_item.arguments)  # OpenAI expects arguments as a JSON string
                        })
                    elif content_item.type == "tool_call_result":
                        input_messages.append({
                            "type": "function_call_output",
                            "call_id": content_item.call_id,
                            "output": content_item.result
                        })
                    else:
                        print(
                            f"Unsupported model message content type for openai chat completion input: {content_item.type}")

        # finally add the user prompt
        prompt = request.prompt
        if prompt and len(prompt) > 0:
            input_messages.append({"role": "user", "content": prompt})

        #  build system instructions
        system_prompt = request.system or [self.DEFAULT_SYSTEM_PROMPT]
        instructions = "\n".join(system_prompt) if isinstance(system_prompt, list) else system_prompt

        output_format = {"type": "text"}
        if request.output_schema:
            schema_name = "OutputSchema"
            output_format = {"type": "json_schema", "schema": request.output_schema, "name": schema_name}
        elif request.output_format == "json":
            output_format = {"type": "json_object"}

        model_params = request.model_parameters or {}
        temperature = model_params.get('temperature', request.temperature) or self.DEFAULT_TEMPERATURE
        max_tokens = model_params.get('max_tokens', request.max_tokens) or self.DEFAULT_MAX_TOKENS
        top_p = model_params.get('top_p', request.top_p) or None
        max_tool_calls = model_params.get('max_tool_calls', self.DEFAULT_MAX_TOOL_CALLS)

        # call OpenAI Responses API
        logger.info(f"OPENAI: Generate completion response with %d input messages:", len(input_messages))
        time_start = time.time()
        model_result = self.client.responses.create(
            model=model,
            instructions=instructions,
            input=input_messages,
            tools=tool_defs_openai or [],
            stream=False,
            text={
                "format": output_format,
            },
            temperature=temperature,
            max_output_tokens=max_tokens,
            max_tool_calls=max_tool_calls,
            top_p=top_p,
        )
        logger.info(model_result)
        time_end = time.time()

        # mapping OpenAI Responses API output format to generic model messages
        output_parts = []
        for output_item in model_result.output:
            if output_item.type == "message":
                for content_item in output_item.content:
                    if content_item.type == "output_text":
                        logger.info(f"Model output text: {content_item.text}")
                        _text = content_item.text
                        _text_part = TextContent(text=_text)
                        if _text.strip().startswith("{") and _text.strip().endswith("}"):
                            logger.info("Looks like the content is JSON, trying to parse it.")
                            try:
                                json_data = json.loads(_text)
                                _text_part = JsonContent(data=json_data)
                            except json.JSONDecodeError:
                                logger.warning(
                                    "Content looks like JSON but failed to parse, adding as plain text.")
                        output_parts.append(_text_part)
                    elif content_item.type == "refusal":
                        logger.critical(f"Model refusal: {content_item.refusal}")
                        output_parts.append(TextContent(text=f"Model refusal: {content_item.refusal}"))

            elif output_item.type == "function_call":
                # https://platform.openai.com/docs/guides/function-calling?api-mode=responses#handling-function-calls
                fn_call_id = output_item.call_id
                fn_name = output_item.name
                fn_args = json.loads(output_item.arguments)
                logger.info(f"Tool call detected: Function {fn_name} with args: {fn_args} ({fn_call_id})")

                output_parts.append(ToolCallContent(name=fn_name, arguments=fn_args, call_id=fn_call_id))
            else:
                logger.warning(f"Unsupported OpenAI response output item type: {output_item.type}")
                output_parts.append(TextContent(text=f"Unsupported OpenAI response item type: {output_item.type}"))

        # Usage
        usage = {
            "input_tokens": model_result.usage.input_tokens,
            "output_tokens": model_result.usage.output_tokens,
            "total_tokens": model_result.usage.total_tokens,
        }
        logger.info(
            f"Tokens used in this chat completion: {usage['total_tokens']}, processing time approx: {time_end - time_start:.8f} seconds")

        return ChatCompletionResponse(
            id=uuid.uuid4().hex,
            timestamp=int(time.time()),
            model=f"{self.name}:{model}",
            prompt=prompt,
            output=output_parts,
            output_text=model_result.output_text,
            model_result=model_result.model_dump()
        )

    def generate_audio_transcription(self, model: str, audio: bytes | str, **kwargs) -> AudioTranscriptionApiResponse:
        if isinstance(audio, bytes):
            # OpenAI API expects a file-like object, so we can use BytesIO
            from io import BytesIO
            audio = BytesIO(audio)
        elif isinstance(audio, str):
            if not os.path.exists(audio):
                raise ValueError(f"Audio file path does not exist: {audio}")
            audio = open(audio, "rb")
        transcript = self.client.audio.transcriptions.create(
            model=model,
            file=audio,
        )
        return AudioTranscriptionApiResponse(
            id=uuid.uuid4().hex,
            timestamp=int(time.time()),
            model=f"{self.name}:{model}",
            output_text=transcript.text
        )

    def generate_image(self, prompt: str, model: str = "dall-e-2", n: int = 1, size: str = "256x256",
                       **kwargs) -> ImageGenerationApiResponse:
        """
        Generate an image using OpenAI's DALL-E model.

        https://platform.openai.com/docs/api-reference/images/create

        :param prompt: The prompt to generate the image.
        :param model: The model to use for image generation.
        :param n: The number of images to generate.
        :param size: The size of the generated image.
        :return: The generated image in base64 format.
        """

        # set response format based on the model
        if kwargs.get('response_format') is None and model != "gpt-image-1":
            # Not supported for gpt-image-1, but required for other models. OpenAI default is 'url'.
            kwargs['response_format'] = "b64_json"
        if kwargs.get('output_format') is None and model == "gpt-image-1":
            # gpt-image-1 supports output_format, but not response_format
            kwargs['output_format'] = "png"

        # check parameters
        if model not in self.DALLE_MODELS:
            raise ValueError(f"Model {model} is not supported by {repr(self)}.")
        if size not in self.DALLE_MODELS[model]['sizes']:
            raise ValueError(f"Size {size} is not supported by model {model}. "
                             f"Supported sizes are: {self.DALLE_MODELS[model]['sizes']}.")

        # Fake response for 'response_format=url' for testing purposes
        if kwargs.get('response_format') == "url":
            # todo Implement cloud storage for images
            return ImageGenerationApiResponse(
                id=uuid.uuid4().hex,
                timestamp=time.time(),
                prompt=prompt,
                model=f"{self.name}:{model}",
                provider=self.name,
                # model_result=img.model_dump(), # skip model_dump() as it contains large data
                output=[{"url": "https://example.com/fake_image.png"}]  # Fake URL for testing
            )

        img = self.client.images.generate(
            model=model,
            prompt=prompt,
            n=n,
            size=size,
            # quality="standard",
            # response_format="b64_json", # omit for gpt-image-1
            # output_format="png", # only gpt-image-1 supports this
            **kwargs  # allow additional parameters
        )

        # image_url = img.data[0].url
        # image_b64 = img.data[0].b64_json
        # image_bytes = base64.b64decode(img.data[0].b64_json)

        # img.data contains either 'b64_json' or 'url' keys
        # wanted [{"base64": "..."}, {"url": "https://..."}]
        def _map_item(item):
            if item.b64_json:
                return {"base64": item.b64_json}
            elif item.url:
                return {"url": item.url}
            else:
                raise ValueError("Image data does not contain 'b64_json' or 'url' key.")

        return ImageGenerationApiResponse(
            id=uuid.uuid4().hex,
            timestamp=time.time(),
            prompt=prompt,
            model=f"{self.name}:{model}",
            provider=self.name,
            # model_result=img.model_dump(), # skip model_dump() as it contains large data
            output=[_map_item(item) for item in img.data]
        )


# export the provider class for easy import
ai_provider_class = OpenAIProvider
