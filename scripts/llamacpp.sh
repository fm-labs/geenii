#!/bin/bash

# This script sets up and runs a Llama.cpp model using Docker.

#docker run -p 8080:8080 -v ./data/models:/models ghcr.io/ggml-org/llama.cpp:server -m models/7B/ggml-model.gguf -c 512 --host 0.0.0.0 --port 8080
docker run -p 8080:8080 -v /Users/phil/.llamabarn:/models:ro ghcr.io/ggml-org/llama.cpp:server -m /models/gemma-3-270m-it-qat-Q4_0.gguf -c 512 --host 0.0.0.0 --port 8080