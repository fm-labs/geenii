# geenii models

List available AI models.

## Synopsis

```
geenii models <command>
```

## Commands

### list

```
geenii models list [OPTIONS]
```

List all available models in a table with name, provider, description,
locality, and capabilities.

#### Options

| Option | Short | Description |
|---|---|---|
| `--provider` | `-p` | Filter by provider name |
| `--locality` | `-l` | Filter by locality |

#### Examples

```bash
# list all models
geenii models list

# only OpenAI models
geenii models list -p openai

# only local models
geenii models list -l local
```
