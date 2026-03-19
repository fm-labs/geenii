
## Quick start with Geenii-in-a-box (Docker Compose)

### Prerequisites

- Docker and Docker Compose installed on your machine. Easiest way is to install is downloading [Docker Desktop](https://www.docker.com/products/docker-desktop).
- Ollama installed for local LLM support (optional but recommended). You can download it from [Ollama's official website](https://ollama.com/download).
- (Optional) An OpenAI API key to use OpenAI cloud models.
- (Optional) Ollama API key to use Ollama's cloud models.
- (Optional) Claude API key to use Anthropic cloud models.
- (Optional) OpenRouter API key to use OpenRouter cloud models.

### Clone the repository

```bash
git clone https://github.com/fm-labs/geenii.git
cd geenii
```

## Configure environment

**Note** the local stack reads env variables from `$HOME/.geenii/.env` file. 
You can create this file and add your API keys there, or you can set the env variables in your shell before running docker compose.


```bash
mkdir -p $HOME/.geenii
touch $HOME/.geenii/.env
echo "OPENAI_API_KEY=your_openai_api_key" >> $HOME/.geenii/.env
echo "OLLAMA_API_KEY=your_ollama_api_key" >> $HOME/.geenii/.env
echo "CLAUDE_API_KEY=your_claude_api_key" >> $HOME/.geenii/.env
echo "OPENROUTER_API_KEY=your_openrouter_api_key" >> $HOME/.geenii/.env
```

### Start the local stack


```bash
docker-compose up
```

→ The API server will be running at `http://localhost:33311`.

→ The WebUI will be available at `http://localhost:33380`.

