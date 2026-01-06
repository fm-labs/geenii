import base64
import json
import time
import uuid

from geenii.provider.interfaces import AIProvider, AICompletionProvider, AIAssistantProvider, AIImageGeneratorProvider
from geenii.datamodels import CompletionApiResponse, ImageGenerationApiResponse
from geenii.provider.openai.client import get_openai_client


class OpenAIProvider(AIProvider, AICompletionProvider, AIAssistantProvider, AIImageGeneratorProvider):
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


    def generate_completion(self, prompt: str, **kwargs) -> CompletionApiResponse:
        """
        Get openai completion for the given prompt via OpenAI Responses API.

        :param prompt: The prompt string to generate a completion for.
        :param kwargs: The keyword arguments for the OpenAI API request.
                        - model: The model to use for the completion (default is 'gpt-3.5-turbo').
        :return:
        """
        model = kwargs.get('model', self.DEFAULT_MODEL)
        system = kwargs.get('system', None)
        stream = kwargs.get('stream', False)
        temperature = kwargs.get('temperature', 0.5)
        max_tokens = kwargs.get('max_tokens', 4096)
        top_p = kwargs.get('top_p', None)
        #top_k = kwargs.get('top_k', None) # top_k is not supported in OpenAI Responses API
        format = kwargs.get('output_format', None)
        if isinstance(format, str):
            if format.lower() == "json" or format.lower() == "json_object":
                format = {"type": "json_object"}
            else:
                raise ValueError(f"Unsupported format: {format}. Supported formats are: 'json' or pass a JSON schema object.")
        #if not isinstance(format, dict):
        #    raise ValueError(f"Format must be a string or a JSON schema object, got {type(format)}.")

        #if model not in self.get_models():
        #    raise ValueError(f"Model {model} is not supported by {repr(self)}.")

        input_messages = kwargs.get('input', [])
        if system is not None:
            input_messages.append({"role": "system", "content": system})
        input_messages.append({"role": "user", "content": prompt})

        model_result = self.client.responses.create(
            model=model,
            instructions=system,
            input=input_messages,
            stream=stream,
            temperature=temperature,
            max_output_tokens=max_tokens,
            text=format,
            top_p=top_p,
        )

        output = [item.model_dump() for item in model_result.output]
        response = CompletionApiResponse(
            id=uuid.uuid4().hex,
            timestamp=int(time.time()),
            prompt=prompt,
            model=model,
            provider=self.name,
            # the output from the model response in OpenAI Responses API format
            output=output,
            # the aggregated text output from all output_text items in the output array
            output_text=model_result.output_text,
            # the full model result for debugging
            model_result=model_result.model_dump()
        )
        return response


    def generate_assistant_completion(self, prompt: str, tool_names: list, **kwargs):
        model = kwargs.get('model', self.DEFAULT_MODEL)
        #if model not in self.get_models():
        #    raise ValueError(f"Model {model} is not supported by {repr(self)}.")

        input_messages = [{"role": "user", "content": prompt}]
        response = self._request_response_with_tools(
            model=model,
            input=input_messages,
            tools=tool_names,
            stream=False
        )
        return response

    def _request_response_with_tools(self, count=0, **kwargs):

        if count > 10:
            print(f"Tool calls made: {count - 1}. Requesting response again with updated messages.")
            raise Exception("Tool calls limit reached.")

        input_messages = kwargs.get('input', [])
        tools = kwargs.get('tools', [])

        print(f"Requesting response ({count}) with input messages:", input_messages)
        response = self.client.responses.create(**kwargs)
        print(f"Response received: {response}")

        def call_function(name, args):
            # resolve_ai_tool_from_name(name)
            # invoke_ai_tool(tool, args)
            if name == "get_weather":
                # Simulate a weather API call
                return f"Current temperature in {args['location']} is 25°C."
            elif name == "get_geolocation_for_location":
                # Simulate a geolocation API call
                return {"latitude": 42.4228, "longitude": -74.0060}
            else:
                return f"Function {name} not implemented."

        tool_calls = 0
        for tool_call in response.output:
            if tool_call.type != "function_call":
                continue

            tool_calls += 1
            name = tool_call.name
            args = json.loads(tool_call.arguments)
            print(f"Calling function: {name} with args: {args}")

            result = call_function(name, args)
            # https://platform.openai.com/docs/guides/function-calling?api-mode=responses#handling-function-calls
            # The suggested way to handle function calls is to return a new response with the updated messages. (NOT WORKING)
            # input_messages.append({
            #     "type": "function_call_output",
            #     "call_id": tool_call.call_id,
            #     "output": str(result)
            # })
            # Append the result to the input messages
            input_messages.append({
                "role": "assistant",
                "content": f"Function call result for {name} with args ({args}): {result}",
            })

            # remove the tool from the tool list, to avoid calling it again
            tools = [tool for tool in tools if tool.get('name') != name]

        # If there are tool calls, we need to create a new response with the updated messages
        if tool_calls > 0:
            kwargs["input"] = input_messages
            kwargs["tools"] = tools
            return self._request_response_with_tools(
                count=count + 1,
                **kwargs
            )

        return response

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