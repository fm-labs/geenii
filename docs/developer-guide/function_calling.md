# function calling

## Geenii API

**Example Request**

```bash
curl -v http://localhost:13030/v1/ai/assistant -H 'Content-Type: application/json' -d '{
  "model": "llama3.2:3b",
  "prompt": "what is the weather in tokyo?",
  "tools": ["get_weather"],
  "stream": false
}'| jq
```

## OpenAI Responses API

**Example Request**

```bash

curl https://api.openai.com/v1/responses \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $OPENAI_API_KEY" \
-d '{
    "model": "gpt-4.1",
    "input": "What is the weather like in Paris today?",
    "tools": [
        {
            "type": "function",
            "name": "get_weather",
            "description": "Get current temperature for a given location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City and country e.g. Bogotá, Colombia"
                    }
                },
                "required": [
                    "location"
                ],
                "additionalProperties": false
            }
        }
    ]
}'
```

## Ollama API

Tools with function calling capabilities:
https://ollama.com/search?c=tool

**Example Request using curl**

```bash
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
```

**Example Request using Python**

```python
import ollama

response = ollama.chat(
    model='llama3.1',
    messages=[{'role': 'user', 'content':
        'What is the weather in Toronto?'}],

    # provide a weather checking tool to the model
    tools=[{
        'type': 'function',
        'function': {
            'name': 'get_current_weather',
            'description': 'Get the current weather for a city',
            'parameters': {
                'type': 'object',
                'properties': {
                    'city': {
                        'type': 'string',
                        'description': 'The name of the city',
                    },
                },
                'required': ['city'],
            },
        },
    },
    ],
)

print(response['message']['tool_calls'])
```


