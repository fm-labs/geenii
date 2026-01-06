import time
import uuid
from typing import List

import ollama

from geenii.provider.interfaces import AIProvider, AICompletionProvider, AIAssistantProvider
from geenii.datamodels import CompletionApiResponse, AssistantApiResponse
from geenii.tools import resolve_tool_defs


class OllamaAIProvider(AIProvider, AICompletionProvider, AIAssistantProvider):

    DEFAULT_MODEL = "mistral:latest"

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

    def generate_completion(self, prompt: str, **kwargs) -> CompletionApiResponse:
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
        temperature = kwargs.get('temperature', 0.5)
        max_tokens = kwargs.get('max_tokens', 4096)
        top_k = kwargs.get('top_k', None)
        top_p = kwargs.get('top_p', None)

        #if model not in self.get_models():
        #    raise ValueError(f"Model {model} is not supported by {repr(self)}.")

        # if system is not None:
        #     prompt="""
        #     System: {system}
        #
        #     User: {prompt}
        #     """

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
            response = CompletionApiResponse(
                id=uuid.uuid4().hex,
                timestamp=int(time.time()),
                prompt=prompt,
                model=model,
                provider=self.name,
                output=[{
                    'id': 'xmsg_' + uuid.uuid4().hex,  # Generate a unique ID for the message
                    'type': 'message',
                    'content': [{
                        'type': 'output_text',
                        'text': content,
                    }]
                }],
                # original model result for debugging
                model_result=model_result.model_dump()
            )
            return response

        except Exception as e:
            print("OLLAMA: Error generating completion:", str(e))
            raise e


    def generate_assistant_completion(self, prompt: str, tool_names: List[str], **kwargs):
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

        :param prompt: The prompt string to generate a completion for.
        :param tool_names: A list of tool names to use for the completion.
                      Each tool should be a string representing the tool name.
                      The tools will be mapped to Ollama's function call format.
        :param kwargs: The keyword arguments for the Ollama API request.
                        - model: The model to use for the completion (default is 'gpt-3.5-turbo').
        :return:
        """
        model = kwargs.get('model', self.DEFAULT_MODEL)
        #if model not in self.get_models():
        #    raise ValueError(f"Model {model} is not supported by {repr(self)}.")

        openai_tools = resolve_tool_defs(tool_names)
        print("Mapped OpenAI tools:", openai_tools)
        ollama_tools = map_openai_tools_to_ollama(openai_tools)
        print("Mapped tools:", ollama_tools)

        messages = kwargs.get('messages', None)
        if messages is None or not isinstance(messages, list):
            messages = []

        if len(messages) == 0:
            messages = [
                {
                    'role': 'system',
                    'content': 'You are a helpful assistant that can call tools to answer questions. If you do not know the answer, you should call a tool to get the information.',
                },
            ]

        # Add the user message to the messages list
        messages.append({
            'role': 'user',
            'content': "Use the available tools to process the prompt: " + prompt,
        })
        try:
            model_result = ollama.chat(
                model=model,
                messages=messages,
                tools=ollama_tools,
                stream=False,
                #format="json",
            )

            print("Model Response:", model_result)
            message = model_result.get('message', default={})
            if not message:
                print("No message found in the model response.")
                raise Exception("No message found in the model response.")

            output = list()

            # Check if the message contains content
            content = message.get('content', '')
            if content:
                print("Content found in the message:", content)
                output.append({
                    'id': 'xmsg_' + uuid.uuid4().hex,  # Generate a unique ID for the message
                    'type': 'message',
                    'content': {
                        'type': 'output_text',
                        'text': content,
                    }
                })
            else:
                print("No content found in the message.")

            # tool calls are returned in response.message
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
            # we need to map them to OpenAI format:
            # [{
            #     "type": "function_call",
            #     "id": "fc_12345xyz",
            #     "call_id": "call_12345xyz",
            #     "name": "get_weather",
            #     "arguments": "{\"location\":\"Paris, France\"}"
            # }]
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

                    output.append({
                        'id': 'xfc_' + uuid.uuid4().hex,  # Generate a unique ID for the function call
                        'call_id': 'xcall_' + uuid.uuid4().hex,  # Generate a unique call ID for the function call
                        'type': 'function_call',
                        'name': name,
                        'arguments': arguments,
                    })

                    # todo invoke the tool and get the result, then append to output

            response = AssistantApiResponse(
                id=uuid.uuid4().hex,
                timestamp=int(time.time()),
                prompt=prompt,
                model=model,
                provider=self.name,
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