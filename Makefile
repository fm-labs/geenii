# Variables
UV_BIN ?= uv

IMAGE?=geenii
TAG?=latest


INFO_COLOR = \033[0;36m
NO_COLOR   = \033[m

.PHONY: help
help:
	@echo "Usage: make [build,image,run-devserver,run-container]"
	@echo "  run-devserver:     Run server in dev mode"
	@echo "  run-container:     Run container"
	@echo "  help:     			Print this help message"


.PHONY: test
test:
	uv run pytest

.PHONY: build
build:
	uv build --wheel


#.PHONY: start-dev
#start-dev:
#	@echo "#Starting development environment..."
#	docker compose --profile dev up -d


.PHONY: run-devserver
run-devserver:
		exec uvicorn --app-dir ./src geenii.server.server:app --port 33311 --reload --log-level debug


.PHONY: image
image:
		@docker build -f ./Dockerfile -t geenii:latest --progress plain .


.PHONY: run-container
run-container: image
		@docker run -it --rm --name geenii-dev geenii:latest
		@echo "Access the admin api at http://local.amatic.com:2002"
