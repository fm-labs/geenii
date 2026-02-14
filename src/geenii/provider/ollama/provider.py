import time
import uuid
from typing import List

import ollama

from geenii.g import get_tool_registry, execute_tool_call
from geenii.provider.interfaces import AIProvider, AICompletionProvider, AIChatCompletionProvider
from geenii.datamodels import CompletionResponse, ChatCompletionResponse, ChatCompletionRequest, TextContent, \
    ModelMessage, CanonicalContent, ToolCallContent


class OllamaAIProvider(AIProvider, AICompletionProvider, AIChatCompletionProvider):

    DEFAULT_MODEL = "mistral:latest"
    DEFAULT_TEMPERATURE = 0.7
    DEFAULT_MAX_TOKENS = 4096
    DEFAULT_TOP_K = None # 20
    DEFAULT_TOP_P = None # 0.9


    """
    A class to represent the Ollama provider for XAI.
    """
    def __init__(self, **kwargs):
        """
        Initializes the OllamaProvider instance.
        """
        super().__init__(name="ollama")
        #self.client = get_ollama_client()

    def get_capabilities(self) -> list[str]:
        return ['completion', 'chat_completion', 'tools']

    def get_models(self) -> list[str]:
        return [
            "mistral:latest",
            "llama3.2:3b",
            "llama3.2:latest",
            "llama3.1:latest",
            "llama3.0:latest",
            "llama2:latest",
        ]

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
        #print("OLLAMA COMPLETION", prompt, kwargs)
        model = kwargs.get('model', self.DEFAULT_MODEL)
        system = kwargs.get('system', None)
        output_format = kwargs.get('output_format', None)
        stream = kwargs.get('stream', False)
        temperature = kwargs.get('temperature', self.DEFAULT_TEMPERATURE)
        max_tokens = kwargs.get('max_tokens', self.DEFAULT_MAX_TOKENS)
        top_k = kwargs.get('top_k', self.DEFAULT_TOP_K)
        top_p = kwargs.get('top_p', self.DEFAULT_TOP_P)

        #if model not in self.get_models():
        #    raise ValueError(f"Model {model} is not supported by {repr(self)}.")

        # if system is not None:
        #     prompt="""
        #     System: {system}
        #
        #     User: {prompt}
        #     """

        print(f"OLLAMA: Generating completion with model: {model}, system: {system}, prompt: {prompt}")

        try:
            model_result = ollama.generate(
                model=model,
                system=system,
                #todo template=template
                prompt=prompt,
                format=output_format,
                stream=stream,
                options={
                    "temperature": temperature,
                    "num_ctx": max_tokens, # Context window size. Same as OpenAI `max_tokens`
                    "top_p": top_p, # Controls nucleus sampling. Same as OpenAI API
                    "top_k": top_k, # Not available in OpenAI API, but can be used in Ollama
                    #todo "repeat_penalty": repeat_penalty # OpenAI = frequency_penalty + presence_penalty
                    #todo "stop": stop, # Stop sequences to end the generation. Same as OpenAI API
                    #todo "seed": seed, # Random seed for reproducibility. OpenAI added seed in 2024 (Beta)
                }
            )

            # or via chat API
            # model_result = ollama.chat(
            #     model=model,
            #     messages=[
            #         {
            #             'role': 'user',
            #             'content': prompt,
            #         },
            #     ],
            #     #format="json",
            #     stream=False,
            # )

            content = model_result.get('response', '')

            output_message = ModelMessage(role='assistant', content=[TextContent(text=content)])

            response = CompletionResponse(
                id=uuid.uuid4().hex,
                timestamp=int(time.time()),
                #prompt=prompt,
                model=model,
                #provider=self.name,
                output=[output_message],
                output_text=str(content).strip(),
                # original model result for debugging
                model_result=model_result.model_dump()
            )
            return response

        except Exception as e:
            print("OLLAMA: Error generating completion:", str(e))
            raise e

    def generate_chat_completion(self, request: ChatCompletionRequest):
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
        :return:
        """
        model = request.model or self.DEFAULT_MODEL
        tools = request.tools or []
        prompt = request.prompt
        #stream = request.stream
        stream = False # for now we will not support streaming in chat completions.
        #if model not in self.get_models():
        #    raise ValueError(f"Model {model} is not supported by {repr(self)}.")
        #output_format = kwargs.get('output_format', None)

        model_params = request.model_parameters or {}
        temperature = model_params.get('temperature', 0.7)
        max_tokens = model_params.get('max_tokens', 4096)
        top_k = model_params.get('top_k', None)
        top_p = model_params.get('top_p', None)

        print("REQUESTED TOOLS:", tools)

        registry = get_tool_registry()
        # filter the registry to get the tool definitions for the requested tools
        tool_defs = registry.list_definitions()
        openai_tools = [tool_def for tool_def in tool_defs if tool_def['name'] in tools]

        #print("Mapped OpenAI tools:", openai_tools)
        ollama_tools = map_openai_tools_to_ollama(openai_tools)
        print("Mapped tools:", ollama_tools)
        print(f"Mapped {len(openai_tools)} OpenAI tools to Ollama format for tools: {tools}")

        # messages in ollama chat api should be in the format:
        # [
        #     {
        #         "role": "user",
        #         "content": "What is the weather in Tokyo?"
        #     },
        #     {
        #         "role": "assistant",
        #         "content": "The weather in Tokyo is sunny."
        #     },
        #     {
        #         "role": "tool",
        #         "tool_calls": [
        #             {
        #                 "function": {
        #                     "name": "get_weather",
        #                     "arguments": {
        #                         "city": "Tokyo"
        #                     }
        #                 },
        #             }
        #         ],
        #         "content": "The weather in Tokyo is sunny."
        #     }
        # ]
        _messages = []

        # system prompt goes first in the messages list
        system_prompt = request.system
        if system_prompt is None:
            system_prompt = "You are a helpful assistant that can call tools to answer questions. Preferably call a tool to get the information."
        _messages.append({
            'role': 'system',
            'content': system_prompt,
        })

        # developer prompt goes after system prompt and before user prompt
        # developer_prompt = request.developer_prompt
        # if developer_prompt is not None:
        #     _messages.append({
        #         'role': 'developer',
        #         'content': developer_prompt,
        #     })

        # if there are existing messages, add them before the user prompt
        messages = request.messages
        if messages:
            if not isinstance(messages, list):
                raise TypeError("messages must be a list")

            # map the messages to the format expected by the Ollama API,
            # and filter out any non-text content for now (todo: support other content types in the future)
            for message in messages:
                role = message.role
                content = message.content
                if not role or not content:
                    print("Invalid message format, missing 'role' or 'content':", message)
                    continue

                for content_item in content:
                    _message = None
                    if content_item.type== 'text':
                        print(f"Adding message with role {role} and text content: {content_item.text}")
                        _message = {
                            'role': role,
                            'content': content,
                        }
                    elif content_item.type == 'tool_call':
                        print(f"Adding message with role {role} and tool call content: {content_item.name} with arguments {content_item.arguments}")
                        _message = {
                            'role': 'tool',
                            'tool_calls': [{
                                'function': {
                                    'name': content_item.name,
                                    'arguments': content_item.arguments,
                                },
                            }],
                            'content': f"[Tool call: {content_item.name}]",
                        }
                    elif content_item.type == 'tool_call_result':
                        print(f"Adding message with role {role} and tool call result content: {content_item.result}")
                        _message = {
                            'role': 'tool',
                            'content': f"[Tool call result: {content_item.result}]",
                        }
                    else:
                        print(f"Skipping message with role {role} and non-text content: {content_item}")

                    if _message is not None:
                        _messages.append(_message)


        # Add the user prompt to the messages list
        _messages.append({
            'role': 'user',
            'content': prompt,
        })
        try:
            print("OLLAMA: Generating chat completion with model:", model, _messages)
            model_result = ollama.chat(
                model=model,
                messages=_messages,
                tools=ollama_tools,
                stream=stream,
                #format="json",
                options={
                    "temperature": temperature,
                    "num_ctx": max_tokens, # Context window size. Same as OpenAI `max_tokens`
                    "top_p": top_p, # Controls nucleus sampling. Same as OpenAI API
                    "top_k": top_k, # Not available in OpenAI API, but can be used in Ollama
                    #todo "repeat_penalty": repeat_penalty # OpenAI = frequency_penalty + presence_penalty
                    #todo "stop": stop, # Stop sequences to end the generation. Same as OpenAI API
                    #todo "seed": seed, # Random seed for reproducibility. OpenAI added seed in 2024 (Beta)
                }
            )

            print("Model Response:", model_result)
            # Check if the response contains a message with content and tool calls
            message = model_result.get('message', default={})
            if not message:
                print("No message found in the model response.")
                raise Exception("No message found in the model response.")

            role = message.get('role', 'assistant')
            output: List[ModelMessage] = []

            # TEXT content
            content = message.get('content')
            if content:
                print("Content found in the message:", content)
                output.append(ModelMessage(role=role, content=[TextContent(text=content)]))
            else:
                print("No content found in the message.")


            # IMAGE content
            images = message.get('images', [])
            if images:
                print(f"{len(images)} image(s) found in the message.")
                for image in images:
                    output.append(ModelMessage(role=role, content=[TextContent(text="[Image content not supported yet]")]))


            # TOOL CALLS
            # "tool_calls": [
            #             {
            #                 "function": {
            #                     "name": "get_weather",
            #                     "arguments": {
            #                         "city": "Tokyo"
            #                     }
            #                 },
            #             }
            #         ]
            tool_calls = message.get('tool_calls', default=[])
            if not tool_calls:
                print("No tool calls found in the response.")
            else:
                print (f"Tool calls found in the response: {len(tool_calls)}", tool_calls)
                for tool_call in tool_calls:
                    function = tool_call.get('function', {})
                    if not function:
                        print("No function found in the tool call.")
                        continue

                    name = function.get('name', '')
                    arguments = function.get('arguments', {})

                    call_id = 'xcall_' + uuid.uuid4().hex  # Generate a reference ID for this function call, which can be used to link the function call message and the tool result message
                    # output.append({
                    #     #'id': 'xfc_' + uuid.uuid4().hex,  # Generate a unique ID for the function call message
                    #     'call_id': call_id,
                    #     'type': 'function_call',
                    #     'name': name,
                    #     'arguments': arguments,
                    # })
                    output.append(ModelMessage(role='tool', content=[ToolCallContent(name=name, arguments=arguments, call_id=call_id)]))

                    # invoke the tool and get the result, then append to output
                    # try:
                    #     tool_result = call_tool(registry, name, **arguments)
                    #     print("> Tool result for", name, "with arguments", arguments, "is", tool_result)
                    #     output.append({
                    #         'id': call_id,
                    #         'type': 'function_call_result',
                    #         'name': name,
                    #         'data': tool_result,
                    #         'status': 'completed'
                    #     })
                    #     _messages.append({
                    #         'role': 'tool',
                    #         'tool_calls': [{
                    #             'function': {
                    #                 'name': name,
                    #                 'arguments': arguments,
                    #             },
                    #         }],
                    #         'content': str(tool_result),
                    #     })
                    # except Exception as e:
                    #     print(f"Error invoking tool {name} with arguments {arguments}: {e}")
                    #     continue


                # now call the model again with the updated messages to get a final response after tool calls
                # model_result = ollama.chat(
                #     model=model,
                #     messages=_messages,
                #     tools=[], # we don't need to pass tools again
                #     stream=False,
                #     #format="json",
                # )
                # print("Final Model Response after tool calls:", model_result)

            response = ChatCompletionResponse(
                id=uuid.uuid4().hex,
                timestamp=int(time.time()),
                prompt=prompt,
                model=model,
                #provider=self.name,
                output=output, # Parsed output from the model response
                model_result=model_result.model_dump(),
                #todo tools_used=[]
            )
            return response

        except Exception as e:
            print("OLLAMA: Error generating assistant completion:", str(e))
            raise e


def map_openai_tools_to_ollama(tools: list) -> list:
    """
    Map OpenAI tool definitions to Ollama tool definitions.
    """
    ollama_tools = []
    for tool in tools:
        ollama_tool = map_openai_tool_to_ollama(tool)
        ollama_tools.append(ollama_tool)
    return ollama_tools


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