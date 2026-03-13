# Developer Guide

## Running the project from sources

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
uv run uvicorn --app-dir ./src --port 33311 server:app --reload --log-level debug
```

### Run server in production mode from sources

```bash
uv run uvicorn --app-dir ./src --port 33311 server:app
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
