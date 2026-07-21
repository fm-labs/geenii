

docker run --rm -it \
  --env-file=.env.docker \
  -e OLLAMA_HOST=host.docker.internal:11434
  --add-host=host.docker.internal:host-gateway \
  geenii:latest agent "Whats uuup?"