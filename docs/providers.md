# Providers & Models

A provider is an adapter between Geenii's request/response models and an LLM
backend's SDK. Models are addressed with a namespaced ID:

```
<provider>:<model_name>
ollama:qwen3:8b          # everything after the first ':' is the model name
openai:gpt-4o-mini
anthropic:claude-opus-4-6
```

`geenii/ai.py` is the dispatch layer: it splits the model ID, instantiates the
provider, and forwards the request. `generate_chat_completion()` additionally
assigns a `context_id`, logs the request/response, and records token usage
(see [configuration.md](configuration.md) for log locations).

## Provider interfaces

`geenii/provider/interfaces.py` defines one base plus one interface per
capability; a provider implements whichever subset it supports:

| Interface | Method |
|---|---|
| `AIProvider` | `is_configured()`, `get_capabilities()`, `get_models()` |
| `AICompletionProvider` | `generate_completion(model, prompt, **kwargs)` |
| `AIChatCompletionProvider` | `generate_chat_completion(request, tool_registry)` — the one the agent runtime uses |
| `AIImageGeneratorProvider` | `generate_image(model, prompt, **kwargs)` |
| `AISpeechGeneratorProvider` | `generate_speech(model, text, **kwargs)` |
| `AIAudioTranscriptionProvider` | `generate_audio_transcription(model, audio, **kwargs)` |
| `AIAudioTranslationProvider` | `generate_audio_translation(model, audio, target_language, **kwargs)` |

All provider calls are synchronous; the agent runtime wraps them in
`asyncio.to_thread`.

## Implemented providers

Active providers are listed in `ai.SUPPORTED_PROVIDERS = ["geenii", "ollama", "openai", "anthropic"]`.
The `fake` provider is also available but not in `SUPPORTED_PROVIDERS` (it is
intended for tests, not enumeration).

### `ollama` — the reference implementation

- **Configured when:** `OLLAMA_HOST` is set (defaults to `http://localhost:11434`);
  `OLLAMA_API_KEY` is sent as a bearer token when present (Ollama Cloud).
- **Capabilities:** completion, chat completion, tool calling, structured JSON
  output (`output_format="json"` or a JSON schema via `output_schema`),
  optimistic JSON parsing of responses that look like JSON.
- **Model listing:** live from the Ollama API; models ending in `-cloud` are
  marked as cloud, everything else as local.
- **Usage stats:** token counts and load/eval durations are mapped into the
  response's `usage` dict.
- Model parameters map to Ollama options: `temperature`, `max_tokens` →
  `num_ctx`, `top_p`, `top_k`. Streaming and thinking output are not yet
  surfaced.

### `openai`

- **Configured when:** `OPENAI_API_KEY` is set.
- **Capabilities:** completion, chat completion, tool calling, image generation
  (`gpt-image-1`, `dall-e-2/3`), audio transcription (`whisper-1`,
  `gpt-4o-transcribe*`).
- **Model listing:** live from the API, filtered to current `gpt*` chat models.

### `anthropic`

- **Configured when:** `ANTHROPIC_API_KEY` is set.
- **Capabilities:** chat completion, tool calling, optimistic JSON parsing
  (same heuristic as Ollama — responses that look like JSON are promoted to
  `JsonContent`).
- **Model listing:** a hardcoded list of known models (`claude-fable-5`,
  `claude-sonnet-5`, `claude-opus-4-8`, `claude-opus-4-7`, `claude-opus-4-6`,
  `claude-haiku-4-5`); all marked as cloud.
- **Defaults:** `temperature=0.2`, `max_tokens=4096`,
  model=`claude-opus-4-6`.
- Tool definitions are converted via `_to_anthropic_tool()` which maps
  the generic `parameters` schema to Anthropic's `input_schema` field.
- Message history maps system messages to Anthropic's top-level `system`
  parameter; `ToolCallContent` → `tool_use` blocks,
  `ToolCallResultContent` → `tool_result` blocks.

### `geenii`

Placeholder self-provider exposing a single `default` model; completion methods
raise `NotImplementedError`. Reserved for routing prompts back into Geenii's
own agents.

### `fake` — test provider

A deterministic provider for testing the agent loop without network access.
Always reports itself as configured.

- **Capabilities:** completion, chat completion, tool calling.
- **Model listing:** a single `fake:test` model (local).
- Responses are drawn from a FIFO queue populated via `enqueue()`,
  `enqueue_parts()`, and `enqueue_tool_call()`. When the queue is empty a
  static fallback (`"I am a fake model."`) is returned.
- All incoming `ChatCompletionRequest` objects are recorded in `provider.requests`
  for assertion in tests.
- Usage stats are hardcoded (`input_tokens=10`, `output_tokens=20`).

The fake provider is instantiated via `get_ai_provider("fake")` but is **not**
in `SUPPORTED_PROVIDERS`, so it does not appear in `enumerate_providers()` or
`enumerate_models()`.

### Not yet implemented

`openrouter` is a recognized name but raises `NotImplementedError`. The `hf/`,
`kokoro/` (TTS), and `whisper/` (STT) provider packages are experimental and
not registered in `SUPPORTED_PROVIDERS`.

## Request/response models

Defined in `geenii/datamodels.py`:

- `ChatCompletionRequest` — model, `system` (list of prompt parts), `prompt`,
  `messages` (history of `ModelMessage`s), `tools` (set of allowed tool names),
  `output_format`/`output_schema`, `model_parameters`, `context_id`.
- `ChatCompletionResponse` — `output: list[ContentPart]`, `usage`, `context_id`,
  the raw provider payload in `model_result`.

The `output` list uses the content-part vocabulary from
`geenii/chat_models.py`: `TextContent`, `JsonContent`, `ToolCallContent`,
`ToolCallResultContent`, `ImageContent`, and friends — a provider-neutral
format that the agent runtime and chat layer share.

## Adding a provider

1. Create `geenii/provider/<name>/provider.py` with a class implementing
   `AIProvider` plus the capability interfaces you support, and expose it as
   `ai_provider_class` at module level.
2. Map `ChatCompletionRequest` → your SDK's format. For tool calling, filter
   `tool_registry.list_definitions()` by `request.tools` and convert with the
   `Tool.to_*` helpers; map returned tool calls to `ToolCallContent` parts
   (generate a `call_id` if the backend doesn't supply one).
3. Export the class as `ai_provider_class` at the module level (all current
   providers do this). Then add the provider to `SUPPORTED_PROVIDERS` and the
   if/elif chain in `ai.get_ai_provider()`. Dynamic discovery via
   `ai_provider_class` is sketched but not active yet.

The Ollama provider is the best template — it exercises system prompts,
history mapping, tool definitions, structured output, and usage accounting.
