# MCP Servers

This documents the supported parameters and response formats for various MCP (Model Context Protocol) servers.

## Configuration

### Local MCP Server

To configure a local MCP server, you can define it in a JSON configuration file as follows:


#### Run with Python (uv)

```json
{
  "mcpServers": {
    "local": {
      "command": "uv",
      "args": [
        "run",
        "uvicorn",
        "--app-dir",
        "./src",
        "--port",
        "14000",
        "server:app"
      ]
    }
  }
}
```


#### Run with Docker and stdio transport

```json
{
  "mcpServers": {
    "duckduckgo": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "mcp/duckduckgo"
      ]
    }
  }
}
```


#### Run with Docker and HTTP transport

```json
{
  "mcpServers": {
    "duckduckgo": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "mcp/duckduckgo",
        "--transport",
        "http",
        "--port",
        "14000"
      ]
    }
  }
}
```

