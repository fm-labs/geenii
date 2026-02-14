import json
import time
import uuid

from geenii.datamodels import CompletionResponse, ImageGenerationApiResponse, ChatCompletionRequest, \
    ChatCompletionResponse, ModelMessage, TextContent, ToolCallContent
from geenii.g import get_tool_registry
from geenii.provider.interfaces import AIProvider, AICompletionProvider, AIChatCompletionProvider, \
    AIImageGeneratorProvider
from geenii.provider.openai.client import get_openai_client


class OpenAIProvider(AIProvider, AICompletionProvider, AIChatCompletionProvider, AIImageGeneratorProvider):
    """
    A class to represent the OpenAI provider for XAI.
    """
    DEFAULT_MODEL = "gpt-3.5-turbo"

    DALLE_MODELS = {
        "gpt-image-1": {"sizes": ["1024x1024", "auto"]},
        "dall-e-2": {"sizes": ["256x256", "512x512", "1024x1024"]},
        "dall-e-3": {"sizes": ["1024x1024", "1792x1024", "1024x1792"]}
    }

    def __init__(self, **kwargs):
        super().__init__(name="openai")
        self.client = get_openai_client()

    def get_capabilities(self) -> list[str]:
        return ['completion', 'chat_completion', 'function_calling']

    def get_models(self) -> list[str]:
        return [
            "gpt-3.5-turbo",
            "gpt-4",
            "gpt-4o-mini",
            "gpt-4.1"]


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
        #top_k = kwargs.get('top_k', None) # top_k is not supported in OpenAI Responses API
        output_format = kwargs.get('output_format', None)
        if isinstance(output_format, str):
            if output_format.lower() == "json" or output_format.lower() == "json_object":
                output_format = {"type": "json_object"}
            else:
                raise ValueError(f"Unsupported format: {output_format}. Supported formats are: 'json' or pass a JSON schema object.")
        #if not isinstance(format, dict):
        #    raise ValueError(f"Format must be a string or a JSON schema object, got {type(format)}.")

        #if model not in self.get_models():
        #    raise ValueError(f"Model {model} is not supported by {repr(self)}.")

        input_messages = kwargs.get('input', [])
        #if system is not None:
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
            #prompt=prompt,
            model=model,
            #provider=self.name,
            # the output from the model response in OpenAI Responses API format
            output=output,
            # the aggregated text output from all output_text items in the output array
            output_text=model_result.output_text,
            # the full model result for debugging
            model_result=model_result.model_dump()
        )
        return response


    def generate_chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        model = request.model or self.DEFAULT_MODEL
        system_instructions = request.system
        prompt = request.prompt
        messages = request.messages or []
        tools = request.tools or []
        #if model not in self.get_models():
        #    raise ValueError(f"Model {model} is not supported by {repr(self)}.")

        # map tool names to tool definitions in openai format
        tool_defs_openai = []
        if tools:
            registry = get_tool_registry()
            # filter the registry to get the (openai) tool definitions for the requested tools
            tool_defs = registry.list_definitions()
            tool_defs_openai = [tool_def for tool_def in tool_defs if tool_def['name'] in tools]
            print(f"OpenAI tools: {tool_defs_openai}")


        # mapping generic model messages to OpenAI Responses API input format
        input_messages = []
        input_messages.append({"role": "user", "content": prompt})

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
                        print(f"Unsupported model message content type for openai chat completion input: {content_item.type}")


        # perform the API call to OpenAI Responses API
        print(f"Requesting response with input messages:", input_messages)
        model_result = self.client.responses.create(
            model=model,
            instructions=system_instructions,
            input=input_messages,
            tools=tool_defs_openai or [],
            stream=False
        )
        print(f"Response received: {model_result}")

        # mapping OpenAI Responses API output format to generic model messages
        output_content = []
        for output_item in model_result.output:
            if output_item.type == "message":
                for content_item in output_item.content:
                    if content_item.type == "output_text":
                        print(f"Model output text: {content_item.text}")
                        output_content.append(TextContent(text=content_item.text))
                    elif content_item.type == "refusal":
                        print(f"Model refusal: {content_item.refusal}")
                        output_content.append(TextContent(text=f"Model refusal: {content_item.refusal}"))

            elif output_item.type == "function_call":
                # https://platform.openai.com/docs/guides/function-calling?api-mode=responses#handling-function-calls
                fn_call_id = output_item.call_id
                fn_name = output_item.name
                fn_args = json.loads(output_item.arguments)
                print(f"Tool call detected: Function {fn_name} with args: {fn_args} ({fn_call_id})")

                output_content.append(ToolCallContent(name=fn_name, arguments=fn_args, call_id=fn_call_id))
            else:
                print(f"Unsupported OpenAI response output item type: {output_item.type}")

        return ChatCompletionResponse(
            id=uuid.uuid4().hex,
            timestamp=int(time.time()),
            model=model,
            prompt=prompt,
            #provider=self.name,
            output=[ModelMessage(role="assistant", content=output_content)],
            output_text=model_result.output_text,
            model_result=model_result.model_dump()
        )


    def generate_image(self, prompt: str, model: str = "dall-e-2", n: int = 1, size: str = "256x256", **kwargs) -> ImageGenerationApiResponse:
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
                model=model,
                provider=self.name,
                #model_result=img.model_dump(), # skip model_dump() as it contains large data
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

        #image_url = img.data[0].url
        #image_b64 = img.data[0].b64_json
        #image_bytes = base64.b64decode(img.data[0].b64_json)

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
            model=model,
            provider=self.name,
            #model_result=img.model_dump(), # skip model_dump() as it contains large data
            output=[_map_item(item) for item in img.data]
        )


# export the provider class for easy import
ai_provider_class = OpenAIProvider