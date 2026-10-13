# geenii Developer Guide

The geenii has a web service daemon that provides an API for managing agents, tools and skills.
It is one of the core component of the OpenGeenii platform, responsible for executing AI agents and handling interactions.


Full developer docs: [docs/index.md](docs/index.md#developer-guide). The server's API is described in
[docs/developer-guide/server.md](docs/developer-guide/server.md), the web UI in
[docs/developer-guide/web-ui.md](docs/developer-guide/web-ui.md).


## Webserver

### Run geenii web server

```bash
uvicorn --app-dir ./src geenii.server.server:app --port 33311
```

### Run geenii web server in dev mode

```bash
uvicorn --app-dir ./src geenii.server.server:app --port 33311 --reload
```


## Docker

### Build the image

```bash
docker build -f ./Dockerfile -t geenii:latest --progress plain .
```

or using the helper script

```bash
./build_image.sh
```

### Run the container

Example:

```bash
docker run --rm -it \
  --env-file=.env.docker \
  -e OLLAMA_HOST=host.docker.internal:11434 \
  --add-host=host.docker.internal:host-gateway \
  geenii:latest \
  $@
```

or using the helper script:

```bash
./run.sh
```