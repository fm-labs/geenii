import time
import uuid
from typing import List
import logging

import ollama

from geenii import config
from geenii.chat.chat_models import TextContent, ToolCallContent, ContentPart, ToolCallResultContent
from geenii.config import CACHE_DIR
from geenii.datamodels import CompletionResponse, ChatCompletionResponse, ChatCompletionRequest, AIModelInfo, \
    ModelMessage
from geenii.provider.interfaces import AIProvider, AICompletionProvider, AIChatCompletionProvider
from geenii.utils.json_util import write_json

logger = logging.getLogger(__name__)


class OllamaAIProvider(AIProvider, AICompletionProvider, AIChatCompletionProvider):
    DEFAULT_MODEL = "qwen:3b"
    DEFAULT_TEMPERATURE = 0.3
    DEFAULT_MAX_TOKENS = 2048
    DEFAULT_TOP_K = None  # 20
    DEFAULT_TOP_P = None  # 0.9

    """
    A class to represent the Ollama provider for XAI.
    """

    def __init__(self, **kwargs):
        """
        Initializes the OllamaProvider instance.
        """
        super().__init__(name="ollama")
        # self.client = get_ollama_client()
        self._client = None

    @property
    def ollama(self):
        if self._client is None:
            headers = {}
            if config.OLLAMA_API_KEY:
                headers['Authorization'] = f"Bearer {config.OLLAMA_API_KEY}"
            self._client = ollama.Client(host=config.OLLAMA_HOST, headers=headers)
        return self._client

    def is_configured(self) -> bool:
        return config.OLLAMA_HOST

    def get_capabilities(self) -> list[str]:
        return ['completion', 'chat_completion', 'tool_calling']

    def get_models(self) -> list[AIModelInfo]:
        models = []
        # map the ollama models to our internal AIModelInfo format
        try:
            ollama_models = self.ollama.list()

            cache_data = {"models": [model.model_dump(mode="json") for model in ollama_models.models]}
            write_json(f"{CACHE_DIR}/ollama.models.json", cache_data)
        except Exception as e:
            logger.error(f"Error fetching models from Ollama: {e}")
            return models

        if ollama_models and ollama_models.models:
            for model in ollama_models.models:
                metadata = dict()
                metadata["size"] = model.size if model.size else None
                metadata["digest"] = model.digest if model.digest else None
                metadata["modified_at"] = model.modified_at.isoformat() if model.modified_at else None
                metadata.update(model.details.model_dump())
                model_info = AIModelInfo(
                    provider=self.name,
                    name=model.model,
                    locality="cloud" if model.model.endswith("-cloud") else "local",
                    description=f"Ollama model {model.model}",
                    capabilities=[],
                    metadata=model.details.model_dump(),
                )
                models.append(model_info)
        return models

    def generate_chat_completion(self, request: ChatCompletionRequest, tool_registry=None) -> ChatCompletionResponse:
        """
        Get ollama completion for the given prompt via Ollama Chat API.

        **Example ollama chat request:
        curl http://localhost:11434/api/chat -d '{
          "model": "llama3.2",
          "messages": [
            {
              "role": "user",
              "content": "what is the weather in tokyo?"
            }
          ],
          "tools": [
            {
              "type": "function",
              "function": {
                "name": "get_weather",
                "description": "Get the weather in a given city",
                "parameters": {
                  "type": "object",
                  "properties": {
                    "city": {
                      "type": "string",
                      "description": "The city to get the weather for"
                    }
                  },
                  "required": ["city"]
                }
              }
            }
          ],
          "stream": false
        }'

        ** Example ollama chat response:
        {
          "model": "llama3.2",
          "created_at": "2025-07-07T20:32:53.844124Z",
          "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [
              {
                "function": {
                  "name": "get_weather",
                  "arguments": {
                    "city": "Tokyo"
                  }
                },
              }
            ]
          },
          "done_reason": "stop",
          "done": true,
          "total_duration": 3244883583,
          "load_duration": 2969184542,
          "prompt_eval_count": 169,
          "prompt_eval_duration": 141656333,
          "eval_count": 18,
          "eval_duration": 133293625
        }

        :param request: The ChatCompletionRequest object containing the prompt, messages, tools, and other parameters for the chat completion.
        :param tool_registry: The registry of available tools that can be used for tool calls in the chat completion.
        :return:
        """
        model = request.model or self.DEFAULT_MODEL
        if model.startswith("ollama:"):
            model = model[len("ollama:"):]

        tools = request.tools or set()
        prompt = request.prompt
        # stream = request.stream
        stream = False  # for now we will not support streaming in chat completions.
        # if model not in self.get_models():
        #    raise ValueError(f"Model {model} is not supported by {repr(self)}.")
        # output_format = kwargs.get('output_format', None)

        model_params = request.model_parameters or {}
        temperature = model_params.get('temperature', self.DEFAULT_TEMPERATURE)
        max_tokens = model_params.get('max_tokens', self.DEFAULT_MAX_TOKENS)
        top_k = model_params.get('top_k', None)
        top_p = model_params.get('top_p', None)

        # TOOLS
        ollama_tools = []
        logger.info(f"Tool registry provided {tool_registry is not None}, tools requested: {tools}")
        if tool_registry is not None and len(tools) > 0:
            # tool_registry = get_tool_registry()
            # filter the registry to get the tool definitions for the requested tools
            tool_defs = tool_registry.list_definitions()
            openai_tools = [tool_def for tool_def in tool_defs if tool_def['name'] in tools]
            # print("Mapped OpenAI tools:", openai_tools)
            ollama_tools = [map_openai_tool_to_ollama(tool_def) for tool_def in openai_tools]
            logger.info(
                f"Mapped {len(openai_tools)} tools to Ollama format, {[tool['function']['name'] for tool in ollama_tools]}")
            print("Mapped tools:", ollama_tools)

        # messages that will be sent to the Ollama API, starting with the system prompt, then developer prompt (if any),
        # then the conversation history messages (if any), and finally the user prompt
        input_messages = []

        # system prompt goes first in the messages list
        system_prompt = request.system
        # if system_prompt is None:
        # todo make default system prompt configurable
        # system_prompt = "You are a helpful assistant, that gives short and concise answers. Always use the tools if you can. If you don't know the answer, say you don't know and don't try to make up an answer. Always use the tools if you can. If you don't know the answer, say you don't know and don't try to make up an answer."

        for system_prompt_part in system_prompt or []:
            input_messages.append({
                'role': 'system',
                'content': system_prompt_part,
            })

        # todo developer prompt goes after system prompt and before user prompt
        # developer_prompt = request.developer_prompt
        # if developer_prompt is not None:
        #     _messages.append({
        #         'role': 'developer',
        #         'content': developer_prompt,
        #     })

        # if there are existing messages, add them before the user prompt
        if request.messages:
            input_messages.extend(model_messages_to_ollama_format(request.messages))

        # Add the user prompt to the messages list
        if prompt:
            input_messages.append({
                'role': 'user',
                'content': prompt,
            })
        elif not prompt and len(request.messages) < 1:
            raise ValueError("At least a prompt or some messages must be provided for chat completion.")

        try:
            print(input_messages)

            logger.info(
                f"OLLAMA: Generating chat completion with model {model} and {len(input_messages)} input messages")

            chat_options = {
                "temperature": temperature,
                "num_ctx": max_tokens,  # Context window size. Same as OpenAI `max_tokens`
                "top_p": top_p,  # Controls nucleus sampling. Same as OpenAI API
                "top_k": top_k,  # Not available in OpenAI API, but can be used in Ollama
                # todo "repeat_penalty": repeat_penalty # OpenAI = frequency_penalty + presence_penalty
                # todo "stop": stop, # Stop sequences to end the generation. Same as OpenAI API
                # todo "seed": seed, # Random seed for reproducibility. OpenAI added seed in 2024 (Beta)
            }
            model_result = self.ollama.chat(
                model=model,
                messages=input_messages,
                tools=ollama_tools,
                stream=stream,
                options=chat_options,
                # Not supported yet
                # format="json",
                # think=None,
                # logprobs=None,
                # top_logprobs=None,
            )
            # print("Model Response:", model_result)

            # Check if the response contains a message with content and tool calls
            message = model_result.get('message', default={})
            if not message:
                raise Exception("No message found in the model response.")

            # Check the done reason to see if the model finished generating a complete response
            done_reason = model_result.get('done_reason', 'unknown')
            if done_reason != 'stop':
                logger.warning(f"Model response done reason is not 'stop', it is '{done_reason}'. This may indicate that the model did not finish generating a complete response.")

            # Container for the parsed output parts from the model response
            output_parts: List[ContentPart] = []

            # Thinking process
            thinking_content = message.get('thinking', None)
            if thinking_content:
                logger.info("Thinking content found in the model response.")
                #output_parts.append(TextContent(text=f"[Thinking]: {thinking_content}"))


            # TEXT contents
            content = message.get('content')
            if content:
                logger.info("Text Content found in the message len=%d", len(content))
                output_parts.append(TextContent(text=content))

            # IMAGE content
            images = message.get('images', [])
            if images:
                logger.info(f"{len(images)} image(s) found in the message.")
                for image in images:
                    output_parts.append(TextContent(text="[Image content not supported yet]"))
                    #todo output_parts.append(ImageContent(image=image))

            # TOOL CALLS
            tool_calls = message.get('tool_calls', default=[])
            if tool_calls:
                logger.info(f"Tool calls found in the response: {len(tool_calls)}")
                for tool_call in tool_calls:
                    function = tool_call.get('function', {})
                    if not function:
                        logger.warning("No function found in the tool call.")
                        continue

                    name = function.get('name', '')
                    arguments = function.get('arguments', {})
                    call_id = 'xcall_' + uuid.uuid4().hex  # Reference ID for this function call
                    output_parts.append(ToolCallContent(name=name, arguments=arguments, call_id=call_id))
                    logger.info(f"Tool call requested: {name} with arguments {arguments} and call_id {call_id}")

            # Usage and performance metrics
            usage = {
                'input_tokens': model_result.get('prompt_eval_count', 0),
                'output_tokens': model_result.get('eval_count', 0),
                'total_tokens': model_result.get('prompt_eval_count', 0) + model_result.get('eval_count', 0),
                'load_duration': model_result.get('load_duration', 0) / 1_000_000, # convert to milliseconds
                'input_duration': model_result.get('prompt_eval_duration', 0) / 1_000_000, # convert to milliseconds
                'output_duration': model_result.get('eval_duration', 0) / 1_000_000, # convert to milliseconds
                'total_duration': model_result.get('total_duration', 0) / 1_000_000, # convert to milliseconds
            }
            logger.info(f"Tokens used in this chat completion: {usage['total_tokens']}, processing time: {usage['total_duration']} ns")

            logger.info("OLLAMA: Chat completion generated with %d output parts", len(output_parts))
            response = ChatCompletionResponse(
                id=uuid.uuid4().hex,
                timestamp=int(time.time()),
                model=f"{self.name}:{model}",
                prompt=prompt,
                # todo remove prompt from response since we already have the messages in the chat completion request
                output=output_parts,  # Parsed output from the model response
                model_result=model_result.model_dump(),
                # todo tools_used=[]
                usage=usage,
            )
            return response

        except Exception as e:
            logger.error("OLLAMA: Error generating chat completion: %s", str(e))
            raise e

    def generate_completion(self, prompt: str, **kwargs) -> CompletionResponse:
        """
        Get ollama completion for the given prompt via Ollama Responses API.

        Available model options can be found in the Ollama documentation:
        https://github.com/ollama/ollama/blob/main/docs/modelfile.md

        ** Example Ollama API generate request:

        curl http://localhost:11434/api/generate -d '{
          "model": "llama3.2",
          "prompt": "Why is the sky blue?",
          "stream": false,
          "options": {
            "num_keep": 5,
            "seed": 42,
            "num_predict": 100,
            "top_k": 20,
            "top_p": 0.9,
            "min_p": 0.0,
            "typical_p": 0.7,
            "repeat_last_n": 33,
            "temperature": 0.8,
            "repeat_penalty": 1.2,
            "presence_penalty": 1.5,
            "frequency_penalty": 1.0,
            "penalize_newline": true,
            "stop": ["\n", "user:"],
            "numa": false,
            "num_ctx": 1024,
            "num_batch": 2,
            "num_gpu": 1,
            "main_gpu": 0,
            "use_mmap": true,
            "num_thread": 8
          }
        }'

        ** Response Ollama API generate response:
        {
          "model": "llama3.2",
          "created_at": "2023-08-04T19:22:45.499127Z",
          "response": "The sky is blue because it is the color of the sky.",
          "done": true,
          "context": [1, 2, 3],
          "total_duration": 4935886791,
          "load_duration": 534986708,
          "prompt_eval_count": 26,
          "prompt_eval_duration": 107345000,
          "eval_count": 237,
          "eval_duration": 4289432000
        }


        :param prompt: The prompt string to generate a completion for.
        :param kwargs: The keyword arguments for the Ollama API request.
                        - model: The model to use for the completion (default is 'gpt-3.5-turbo').
        :return:
        """
        # print("OLLAMA COMPLETION", prompt, kwargs)
        model = kwargs.get('model', self.DEFAULT_MODEL)
        system = kwargs.get('system', None)
        output_format = kwargs.get('output_format', None)
        stream = kwargs.get('stream', False)
        temperature = kwargs.get('temperature', self.DEFAULT_TEMPERATURE)
        max_tokens = kwargs.get('max_tokens', self.DEFAULT_MAX_TOKENS)
        top_k = kwargs.get('top_k', self.DEFAULT_TOP_K)
        top_p = kwargs.get('top_p', self.DEFAULT_TOP_P)

        print(f"OLLAMA: Generating completion with model: {model}, system: {system}, prompt: {prompt}")
        try:
            model_result = self.ollama.generate(
                model=model,
                system=system,
                # todo template=template
                prompt=prompt,
                format=output_format,
                stream=stream,
                options={
                    "temperature": temperature,
                    "num_ctx": max_tokens,  # Context window size. Same as OpenAI `max_tokens`
                    "top_p": top_p,  # Controls nucleus sampling. Same as OpenAI API
                    "top_k": top_k,  # Not available in OpenAI API, but can be used in Ollama
                    # todo "repeat_penalty": repeat_penalty # OpenAI = frequency_penalty + presence_penalty
                    # todo "stop": stop, # Stop sequences to end the generation. Same as OpenAI API
                    # todo "seed": seed, # Random seed for reproducibility. OpenAI added seed in 2024 (Beta)
                }
            )

            response_text = model_result.get('response', 'No response generated.')
            response = CompletionResponse(
                id=uuid.uuid4().hex,
                timestamp=int(time.time()),
                model=f"{self.name}:{model}",
                # prompt=prompt,
                output=[TextContent(text=response_text)],
                output_text=str(response_text).strip(),
                model_result=model_result.model_dump()
            )
            return response

        except Exception as e:
            print("OLLAMA: Error generating completion:", str(e))
            raise e


def model_messages_to_ollama_format(messages: List[ModelMessage]) -> List[dict]:
    """
    Map our internal ModelMessage format to the format expected by the Ollama API.

    :param messages: A list of ModelMessage objects representing the conversation history.
    :return: A list of dictionaries formatted according to the Ollama API requirements for chat messages.
    """
    ollama_messages = []
    if messages:
        if not isinstance(messages, list):
            raise TypeError("messages must be a list")

        # map the messages to the format expected by the Ollama API,
        # and filter out any non-text content for now (todo: support other content types in the future)
        for message in messages:
            role = message.role
            content = message.content
            if not role or not content:
                logger.warning("Invalid message format, missing 'role' or 'content'")
                print(message)
                #continue

            for content_item in content:
                _message = None
                if isinstance(content_item, TextContent):
                    # print(f"Adding message with role {role} and text content: {content_item.text}")
                    _message = {
                        'role': role,
                        'content': content_item.text,
                    }
                elif isinstance(content_item, ToolCallContent):
                    # print(f"Adding message with role {role} and tool call content: {content_item.name} with arguments {content_item.arguments}")
                    _message = {
                        'role': 'tool',
                        'tool_calls': [{
                            'function': {
                                'name': content_item.name,
                                'arguments': content_item.arguments,
                            },
                        }],
                        'content': f"Tool call: {content_item.name} with arguments {content_item.arguments}",
                    }
                elif isinstance(content_item, ToolCallResultContent):
                    # print(f"Adding message with role {role} and tool call result content: {content_item.result}")
                    _message = {
                        'role': 'tool',
                        'content': f"Tool call result: {str(content_item.result)}",
                    }
                else:
                    logger.warning(f"Unknown content type: {content_item.type}")
                    _message = {
                        'role': role,
                        'content': f"[{content_item.type}] {content_item.to_text()}",
                    }

                if _message is not None:
                    ollama_messages.append(_message)
    return ollama_messages


def map_openai_tool_to_ollama(tool: dict) -> dict:
    """
    Map OpenAI tool definition to Ollama tool definition.

    OpenAI tool definitions typically look like this:
    {
        "type": "function",
        "name": "get_weather",
        "description": "Get the weather in a given city",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "The city to get the weather for"
                }
            },
            "required": ["city"]
        }
    }
    """
    if 'type' not in tool:
        raise ValueError("Tool definition must include a 'type' field.")

    if tool['type'] != 'function':
        raise ValueError("Ollama only supports function type tools.")

    if 'name' not in tool:
        raise ValueError("Tool definition must include a 'name' field.")

    return {
        'type': 'function',
        'function': {
            'name': tool['name'],
            'description': tool.get('description', ''),
            'parameters': tool.get('parameters', {}),
        }
    }


ai_provider_class = OllamaAIProvider
