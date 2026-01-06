
FROM python:3.14.2-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src
ENV PATH="/app/.venv/bin:$PATH"

#ENV API_HOST=0.0.0.0
#ENV API_PORT=13030
#ENV API_DEBUG=1

# Ref: https://docs.astral.sh/uv/guides/integration/docker/#compiling-bytecode
#ENV UV_COMPILE_BYTECODE=1

# Ref: https://docs.astral.sh/uv/guides/integration/docker/#caching
ENV UV_LINK_MODE=copy

# Create a non-root user and group and set permissions for app and home directory
RUN groupadd -r app && useradd -r -g app app && \
    mkdir -p /app && \
    chown -R app:app /app && \
    mkdir -p /home/app && \
    chown -R app:app /home/app && \
    usermod -a -G root app

# Install system dependencies
RUN apt update && apt install -yy \
    bash \
    curl \
    git \
    docker-cli \
    docker-compose \
    && apt clean \
    && rm -rf /var/lib/apt/lists/*

# Install the MCP Gateway CLI (docker-mcp) to the Docker plugin path
#RUN mkdir -p /home/app/.docker/cli-plugins \
# && curl -fL -o /tmp/docker-mcp.tar.gz \
#      https://github.com/docker/mcp-gateway/releases/download/v0.30.0/docker-mcp-linux-amd64.tar.gz \
# && tar -xzf /tmp/docker-mcp.tar.gz -C /home/app/.docker/cli-plugins/ \
# && chmod +x /home/app/.docker/cli-plugins/docker-mcp \
# && rm /tmp/docker-mcp.tar.gz

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
#RUN pip install --no-cache-dir uv


WORKDIR /app

# Install python dependencies
COPY ./pyproject.toml ./uv.lock /app/
RUN uv sync --no-cache-dir

COPY ./src/geenii /app/src/geenii
COPY ./src/server.py /app/src/

# Run
USER app
CMD ["uv", "run", "uvicorn", "--app-dir", "/app/src", "--host", "0.0.0.0", "--port", "13030", "server:app"]
EXPOSE 13030

# Health check
HEALTHCHECK --interval=60s --timeout=3s --retries=3 \
 CMD curl --fail http://localhost:13030/api/health || exit 1
