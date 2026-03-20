FROM python:3.14-alpine AS builder
WORKDIR /builder

# Install build dependencies for pyinstaller
RUN apk add --no-cache \
    bash \
    build-base \
    python3-dev
# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
# Install python dependencies
COPY ./pyproject.toml ./uv.lock /builder/
RUN uv sync --no-cache-dir --frozen --no-install-project --no-dev

COPY ./src/geenii /builder/src/geenii
COPY ./src/cli.py ./src/mod.py ./src/server.py /builder/src/
COPY ./build_bin.sh /builder/build_bin.sh
RUN ls -la /builder
RUN mkdir -p ./build && mkdir -p ./dist && \
    chmod +x /builder/build_bin.sh && \
    bash /builder/build_bin.sh


FROM python:3.14-alpine

# Install system dependencies
RUN apk add --no-cache \
    bash \
    curl \
    git \
    nodejs \
    npm \
    docker-cli \
    docker-compose \
    openssl \
    openssh-client \
    && rm -rf /var/cache/apk/* \
    && npm i -g pnpm

# Create non-root user and group, set permissions for geenii and home directory
RUN addgroup --gid 33311 -S geenii && adduser --uid 33311 -S geenii -G geenii && \
    mkdir -p /geenii && \
    chown -R geenii:geenii /geenii && \
    mkdir -p /home/geenii && \
    chown -R geenii:geenii /home/geenii && \
    mkdir -p /data && \
    chown -R geenii:geenii /data

# Binaries
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY --from=builder /builder/dist/bin/geenii /usr/bin/geenii
COPY --from=builder /builder/dist/bin/geeniimod /usr/bin/geeniimod
COPY --from=builder /builder/dist/bin/geeniid /usr/bin/geeniid

# Entrypoint
COPY ./container/entrypoint.sh /usr/bin/entrypoint
RUN ["chmod", "+x", "/usr/bin/entrypoint"]
ENTRYPOINT ["/usr/bin/entrypoint"]

WORKDIR /home/geenii
USER geenii
ENV GEENII_USER_DIR=/.geenii
ENV GEENII_DATA_DIR=/data
CMD ["geenii", "--help"]
