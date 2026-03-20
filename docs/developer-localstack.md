
## Developer Local Stack

```yaml
services:

  geenii-local:
    build:
      context: .
      dockerfile: Dockerfile-localserver
    ports:
      - "33311:33311"
    networks:
      - geenii-net
    extra_hosts:
      - "host.docker.internal:host-gateway"
    volumes:
      - ./data:/data
      - ./geenii:/home/geenii/.geenii
    environment:
      - OLLAMA_HOST=http://host.docker.internal:11434
      - OLLAMA_API_KEY=${OLLAMA_API_KEY:-}
      - OPENAI_API_KEY=${OPENAI_API_KEY:-}
      - GEMINI_API_KEY=${GEMINI_API_KEY:-}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
      - GITHUB_TOKEN=${GITHUB_TOKEN:-}
```


### Clone the repository

```bash
git clone https://github.com/fm-labs/geenii.git
cd geenii
```

## Configure environment

```bash
touch .env
echo "OLLAMA_HOST=http://host.docker.internal:11434" >> .env
echo "OLLAMA_API_KEY=your_ollama_api_key" >> .env
echo "OPENAI_API_KEY=your_openai_api_key" >> .env
echo "CLAUDE_API_KEY=your_claude_api_key" >> .env
echo "OPENROUTER_API_KEY=your_openrouter_api_key" >> .env
```

Docker compose will automatically load the environment variables from the `.env` file 
and injects the vars in the compose file (not the container!).


### Start the local stack

```bash
mkdir -p .geenii
docker-compose up
```

→ The API server will be running at `http://localhost:33311`.

→ The WebUI will be available at `http://localhost:33380`.

