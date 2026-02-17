# g33n11

Hybrid AI platform for local and remote large language models (LLMs)

- Use remote and local large-language-models seamlessly.
- Build and run your own chat assistants, autonomous agents and AI workflows with ease.
- Supports models from Ollama, OpenAI, HuggingFace, Local LLMs and more.
- Rich toolset for assistants and agents supporting python functions and serverless functions
- Integrates with MCP for orchestration and tooling capabilities.
- Runs locally with docker compose.


## Goals

- **Local-first and Privacy-first** approach to AI workloads.
- Provide a **unified API** for accessing different LLM providers and models.
- Enable easy switching between **local and remote models**.
- Facilitate building AI applications and agents that can leverage multiple models.
- Offer a **self-hosted solution for privacy and control** over AI workloads.
- Enable developers to build and deploy **AI applications without relying on cloud providers**.
- Focus on modularity and extensibility to support new models and providers easily.
- **Focus on MCP integration for maximum tooling and orchestration capabilities**.
- Aims for interoperability with other agent frameworks (e.g., via Agent Protocol).


## Getting Started

### Prerequisites

- Docker and Docker Compose installed on your machine. Easiest way is to install is downloading [Docker Desktop](https://www.docker.com/products/docker-desktop).
- Ollama installed for local LLM support (optional but recommended). You can download it from [Ollama's official website](https://ollama.com/download).
- (Optional) An OpenAI API key if you want to use OpenAI cloud models.
- (Optional) Ollama API key if you want to use Ollama's cloud models.
- (Optional) Claude API key if you want to use Anthropic cloud models.
- (Optional) OpenRouter API key if you want to use OpenRouter cloud models.

### Clone the repository

```bash
git clone https://github.com/fm-labs/geenii.git
cd geenii
```

### Start the local stack

```bash
docker-compose up
```


→ The API server will be available at `http://localhost:13030`.

→ The WebUI will be available at `http://localhost:13031`.




## For Developers

### Prerequisites

- Python 3.13 or higher installed on your machine.
- uv for package management and build tool. You can install it with pip: `pip install uv`
- Node.js and pnpm for building the Web UI. You can install Node.js from [nodejs.org](https://nodejs.org/) and then install pnpm with npm: `npm install -g pnpm`.
- Rust toolchain for building the Desktop UI. You can install it from [rustup.rs](https://rustup.rs/).
- Tauri dependencies. See the official [Tauri documentation for the latest requirements](https://tauri.app/start/prerequisites/)
- Additionally, for Ubuntu/Debian-based systems, you may need to install the following dependencies for building Tauri applications:
  ```bash
  sudo apt update
  sudo apt install -y build-essential libssl-dev libgtk-3-dev libayatana-appindicator3-dev libxdo-dev librsvg2-dev
  ```
- Additionally, for CentOS/RHEL-based systems, you may need to install the following dependencies for building Tauri applications:
  ```bash
  sudo yum install -y gcc openssl-devel libappindicator-gtk3-devel gtk3-devel libxdo-devel librsvg2-devel libsoup-devel webkit2gtk-4.1-devel
  ```
- (Optional) Docker and Docker Compose installed on your machine. Easiest way is to install is downloading [Docker Desktop](https://www.docker.com/products/docker-desktop).


### Install dependencies

```bash
# Python dependencies
uv sync

# UI dependencies
cd ui
pnpm install
```


### Run server in development mode from sources

```bash
uv run uvicorn --app-dir ./src --port 13030 server:app --reload
```

### Run server in production mode from sources

```bash
uv run uvicorn --app-dir ./src --port 13030 server:app
```

### Run desktop UI in development mode

```bash
cd ui
pnpm tauri dev
```

### Run web UI in development mode

```bash
cd ui
pnpm run dev
```


### Run docker compose for development

```bash
docker-compose up --watch
```



### Testing

To run tests, use the following command:

```bash
pytest src/
```
