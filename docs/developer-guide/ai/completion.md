# completion

Request a text completion from an AI model.

## Available Parameters

| Parameter        | Type    | Description                                                                                                                                                                                                                     |
|------------------|---------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| model            | string  | The model to use for the completion. This can be a specific model name or an alias.                                                                                                                                             |
| prompt           | string  | The input text to complete. This is the starting point for the AI model to generate a response.                                                                                                                                 |
| stream           | boolean | If true, the response will be streamed back in chunks. If false, the response will be returned as a single object.                                                                                                              |
| temperature      | float   | Controls the randomness of the output. Higher values (e.g., 0.8) make the output more random, while lower values (e.g., 0.2) make it more focused and deterministic.                                                            |
| top_p            | float   | Nucleus sampling parameter. It controls the diversity of the output by limiting the model to consider only the top `p` probability mass. For example, `top_p=0.9` means only the top 90% of the probability mass is considered. |
| max_tokens       | integer | The maximum number of tokens to generate in the completion. This limits the length of the response.                                                                                                                             |
| output_format    | string  | Specifies the desired format for the response output. This can be used to control how the response is structured (e.g., JSON, plain text).                                                                                      |
| model_parameters | object  | Model-specific parameters.                                                                                                                                                                                                      |


## Parameter Support

| Parameter        | xai | ollama | openai (Responses) | openai (Completion) |
|------------------|-----|--------|--------------------|---------------------|
| model            | ✅   | ✅      | ✅                  | ✅                   |
| prompt           | ✅   | ✅      | ✅                  | ✅                   |
| stream           | ✅   | ✅      | ✅                  | ✅                   |
| temperature      | ✅   | ✅      | ✅                  | ✅                   |
| top_p            | ✅   | ✅      | ✅                  | ✅                   |
| max_tokens       | ✅   | ✅      | ✅                  | ✅                   |
| output_format    | ✅   | ✅      | ✅                  | ✅                   |
| model_parameters | ✅   | ✅      | ✅                  | ?                   |



## xai

### Rest API

#### Models

##### CompletionApiRequest

| Field           | Type            | Default Value            | Required | Description                                              |
|-----------------|-----------------|--------------------------|----------|----------------------------------------------------------|
| `prompt`        | `str`           | None                     | ✓        | The input prompt for the completion                      |
| `model`         | `str \| None`   | `settings.DEFAULT_MODEL` | ✗        | Model identifier to use for completion                   |
| `temperature`   | `float \| None` | `None`                   | ✗        | Controls randomness in model output (0.0-1.0)            |
| `top_p`         | `float \| None` | `None`                   | ✗        | Nucleus sampling parameter for output diversity          |
| `max_tokens`    | `int \| None`   | `None`                   | ✗        | Maximum number of tokens to generate                     |
| `output_format` | `str \| None`   | `None`                   | ✗        | Desired format for the response output                   |
| `stream`        | `bool \| None`  | `False`                  | ✗        | Whether to stream the response or return complete result |

##### CompletionApiResponse

| Field          | Type                 | Default Value | Required | Description                                      |
|----------------|----------------------|---------------|----------|--------------------------------------------------|
| `id`           | `str`                | None          | ✓        | Unique identifier for the completion request     |
| `timestamp`    | `float`              | None          | ✓        | Unix timestamp when the completion was processed |
| `prompt`       | `str`                | None          | ✓        | The original prompt that was submitted           |
| `model`        | `str \| None`        | `None`        | ✗        | The model that was used for the completion       |
| `provider`     | `str \| None`        | `None`        | ✗        | The service provider that handled the request    |
| `model_result` | `dict`               | `None`        | ✗        | Raw result data from the model                   |
| `output`       | `List[dict] \| None` | `None`        | ✗        | Structured output data as list of dictionaries   |
| `output_text`  | `str \| None`        | `None`        | ✗        | Plain text representation of the completion      |
| `error`        | `str \| None`        | `None`        | ✗        | Error message if the completion failed           |


#### Request

```bash
curl -v http://localhost:13030/v1/ai/completion -H 'Content-Type: application/json' -d '{
  "model": "ollama:llama3.2:3b",
  "prompt": "Tell a one-liner joke about AI",
  "stream": false
}'
```

#### Response

```bash
{
  "id": "7ea4a2b31c794dbfac026527e1998695",
  "timestamp": 1753688680.7711308,
  "prompt": "Tell a one-liner joke about AI",
  "model": "llama3.2:3b",
  "provider": "ollama",
  "model_result": {
    "model": "llama3.2:3b",
    "created_at": "2025-07-28T07:44:40.769189Z",
    "done": true,
    "done_reason": "stop",
    "total_duration": 289912875,
    "load_duration": 26226875,
    "prompt_eval_count": 33,
    "prompt_eval_duration": 121848583,
    "eval_count": 20,
    "eval_duration": 141475875,
    "response": "Why did the AI program go to therapy? It had a lot of bytes to work through.",
    "thinking": null,
    "context": [
      128006,
      9125,
      128007,
      ...
    ]
  },
  "output": [
    {
      "id": "xmsg_1bb7c76db9dd4f26bbfe6990cb351e3c",
      "type": "message",
      "content": {
        "type": "output_text",
        "text": "Why did the AI program go to therapy? It had a lot of bytes to work through."
      }
    }
  ],
  "output_text": null,
  "error": null
}
```


## OpenAI APIs

### Completion API (deprecated)

#### Example Request

```bash
curl https://api.openai.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "gpt-4.1",
    "messages": [
      {
        "role": "developer",
        "content": "You are a helpful assistant."
      },
      {
        "role": "user",
        "content": "Hello!"
      }
    ]
  }'
```

#### Example Response

```json
{
  "id": "chatcmpl-B9MBs8CjcvOU2jLn4n570S5qMJKcT",
  "object": "chat.completion",
  "created": 1741569952,
  "model": "gpt-4.1-2025-04-14",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! How can I assist you today?",
        "refusal": null,
        "annotations": []
      },
      "logprobs": null,
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 19,
    "completion_tokens": 10,
    "total_tokens": 29,
    "prompt_tokens_details": {
      "cached_tokens": 0,
      "audio_tokens": 0
    },
    "completion_tokens_details": {
      "reasoning_tokens": 0,
      "audio_tokens": 0,
      "accepted_prediction_tokens": 0,
      "rejected_prediction_tokens": 0
    }
  },
  "service_tier": "default"
}
```


#### Example Request 2

```bash
curl https://api.openai.com/v1/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "gpt-3.5-turbo-instruct",
    "prompt": "Say this is a test",
    "max_tokens": 7,
    "temperature": 0
  }'

```


#### Example Response 2

```json
{
  "id": "cmpl-uqkvlQyYK7bGYrRHQ0eXlWi7",
  "object": "text_completion",
  "created": 1589478378,
  "model": "gpt-3.5-turbo-instruct",
  "system_fingerprint": "fp_44709d6fcb",
  "choices": [
    {
      "text": "\n\nThis is indeed a test",
      "index": 0,
      "logprobs": null,
      "finish_reason": "length"
    }
  ],
  "usage": {
    "prompt_tokens": 5,
    "completion_tokens": 7,
    "total_tokens": 12
  }
}
```