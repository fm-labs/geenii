#!/bin/bash
set -x

BASE_URL="http://localhost:13030"

CMD=$1
if [ -z "$CMD" ]; then
  echo "Usage: $0 <command>"
  echo "Available commands: generate, tools, chat, chatstream"
  exit 1
fi

case "$CMD" in
  generate)
    echo "Generating text..."
    curl -v --header "Content-Type: application/json" \
         --request POST \
         --data '{"model": "ollama:mistral:latest", "prompt": "Tell a one-liner adventure of a flying unicorn"}' \
         $BASE_URL/ai/v1/completion
    ;;
  tools)
    echo "Using tools..."
    curl -v --header "Content-Type: application/json" \
         --request POST \
         --data '{"model": "ollama:mistral:latest", "tools": ["get_weather", "get_geolocation_for_location", "calculate_two_numbers", "get_stock_price"], "prompt": "Get the weather of Bogota and New York. Where is the better temperature. Temperature in degree Celsius. Use tools."}' \
         $BASE_URL/ai/v1/completion
    ;;
  chat)
    echo "Starting chat session..."
    ;;
  chatstream)
    echo "Starting chat stream..."
    ;;
  mcp-servers)
    echo "List MCP servers..."
    curl -v --header "Content-Type: application/json" \
         --request GET \
         $BASE_URL/api/mcp/servers
    ;;
  mcp-tools)
    echo "List MCP tools..."
    curl -v --header "Content-Type: application/json" \
         --request GET \
         $BASE_URL/api/mcp/tools
    ;;
  mcp-tool)
    if [ -z "$2" ]; then
      echo "Usage: $0 mcp-tool <tool_name>"
      exit 1
    fi
    TOOL_NAME=$2
    echo "Using MCP tool: $TOOL_NAME"
    curl -v --header "Content-Type: application/json" \
         --request POST \
         --data "{\"tool\": \"$TOOL_NAME\", \"args\": {}}" \
         $BASE_URL/api/mcp/tool
    ;;
  mcp-tool-search)
    if [ -z "$2" ]; then
      echo "Usage: $0 mcp-tool-search <query>"
      exit 1
    fi
    TOOL_NAME=duckduckgo_search
    QUERY=$2
    echo "Searching MCP tools for: $QUERY"
    curl -v --header "Content-Type: application/json" \
         --request POST \
         --data "{\"tool_name\": \"$TOOL_NAME\", \"arguments\": {\"query\": \"$QUERY\"}}" \
         $BASE_URL/api/mcp/call_tool
    ;;
  *)
    echo "Unknown command: $CMD"
    exit 1
    ;;
esac
