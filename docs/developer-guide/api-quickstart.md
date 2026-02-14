# API Quickstart Guide

## Generate completion

**Ollama Example:**

In the example we use **ollama:mistral:latest** to generate text completions locally.

```bash
curl -X POST http://localhost:13030/ai/v1/completion \
  -H "Content-Type: application/json" \
  -d '{
    "model": "ollama:mistral:latest",
    "prompt": "Tell me a joke about AI"
  }' | jq
```

```bash
{
  "id": "7deaec0ff75e465082ac0a3bbc4e691c",
  "timestamp": 1767641486,
  "model": "mistral:latest",
  "provider": "ollama",
  "error": null,
  "model_result": {
    "model": "mistral:latest",
    "created_at": "2026-01-05T19:31:26.74049Z",
    "done": true,
    "done_reason": "stop",
    "total_duration": 3221822417,
    "load_duration": 2222144375,
    "prompt_eval_count": 10,
    "prompt_eval_duration": 203207542,
    "eval_count": 65,
    "eval_duration": 713572252,
    "response": " Why don't AI programmers trust atoms?\n\nBecause they make up everything, even if you ignore them! (A play on the phrase \"They make up everything,\" which is often used to mean that something is not true or just a story, and the fact that atoms are fundamental building blocks of matter.)",
    "thinking": null,
    "context": [
      3,
      29473,
      16027,
      1296,
      ...
    ],
    "logprobs": null
  },
  "prompt": "Tell me a joke about AI",
  "output": [
    {
      "id": "xmsg_d505b4e23f5d4aab902cac4d2051b531",
      "type": "message",
      "content": [
        {
          "type": "output_text",
          "text": " Why don't AI programmers trust atoms?\n\nBecause they make up everything, even if you ignore them! (A play on the phrase \"They make up everything,\" which is often used to mean that something is not true or just a story, and the fact that atoms are fundamental building blocks of matter.)"
        }
      ]
    }
  ],
  "output_text": null
}
```

**OpenAI Example:**

In this example we use **openai:gpt-4o-mini** to generate text completions via OpenAI API.

```bash
curl -X POST http://localhost:13030/ai/v1/completion \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai:gpt-4o-mini",
    "prompt": "Tell me a joke about AI"
  }' | jq
```

```bash
{
  "id": "dd3c7c67d2e24b679b0a2c60e89c581c",
  "timestamp": 1767641510,
  "model": "gpt-4o-mini",
  "provider": "openai",
  "error": null,
  "model_result": {
    "id": "resp_0d8550ccdaa2c10900695c11a5423c81968d7250de066904b6",
    "created_at": 1767641509.0,
    "error": null,
    "incomplete_details": null,
    "instructions": null,
    "metadata": {},
    "model": "gpt-4o-mini-2024-07-18",
    "object": "response",
    "output": [
      {
        "id": "msg_0d8550ccdaa2c10900695c11a625e88196b88190a9903c5b4f",
        "content": [
          {
            "annotations": [],
            "text": "Why did the AI go broke?\n\nBecause it lost its cache!",
            "type": "output_text",
            "logprobs": []
          }
        ],
        "role": "assistant",
        "status": "completed",
        "type": "message"
      }
    ],
    "parallel_tool_calls": true,
    "temperature": 0.5,
    "tool_choice": "auto",
    "tools": [],
    "top_p": 1.0,
    "background": false,
    "conversation": null,
    "max_output_tokens": 4096,
    "max_tool_calls": null,
    "previous_response_id": null,
    "prompt": null,
    "prompt_cache_key": null,
    "prompt_cache_retention": null,
    "reasoning": {
      "effort": null,
      "generate_summary": null,
      "summary": null
    },
    "safety_identifier": null,
    "service_tier": "default",
    "status": "completed",
    "text": {
      "format": {
        "type": "text"
      },
      "verbosity": "medium"
    },
    "top_logprobs": 0,
    "truncation": "disabled",
    "usage": {
      "input_tokens": 13,
      "input_tokens_details": {
        "cached_tokens": 0
      },
      "output_tokens": 14,
      "output_tokens_details": {
        "reasoning_tokens": 0
      },
      "total_tokens": 27
    },
    "user": null,
    "billing": {
      "payer": "developer"
    },
    "completed_at": 1767641510,
    "store": true
  },
  "prompt": "Tell me a joke about AI",
  "output": [
    {
      "id": "msg_0d8550ccdaa2c10900695c11a625e88196b88190a9903c5b4f",
      "content": [
        {
          "annotations": [],
          "text": "Why did the AI go broke?\n\nBecause it lost its cache!",
          "type": "output_text",
          "logprobs": []
        }
      ],
      "role": "assistant",
      "status": "completed",
      "type": "message"
    }
  ],
  "output_text": "Why did the AI go broke?\n\nBecause it lost its cache!"
}
```

The anatomy of the response is similar across different providers, with the `model_result` field containing the raw response from the model provider.

The `output` field contains a OpenAI Responses API style representation of the model's output, which can include text, images, or other data types depending on the model used.


## Generate image completion

```bash
curl -X POST http://localhost:13030/ai/v1/image/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai:dall-e-2",
    "prompt": "A funky cat"
  }' | jq
```
