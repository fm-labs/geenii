FROM python:3.14-alpine AS builder
WORKDIR /builder

# Install build dependencies for pyinstaller
RUN apk add --no-cache \
    bash \
    build-base \
    python3-dev \
    libffi-dev zlib-dev curl ccache zstd-dev
# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
# Install python dependencies
COPY ./pyproject.toml ./uv.lock /builder/
RUN uv sync --no-cache-dir --frozen --no-install-project

COPY ./src/geenii /builder/src/geenii
COPY ./README.md /builder/

# build using pyinstaller
COPY ./hooks /builder/hooks
#COPY ./build_bin.sh /builder/build.sh
COPY ./build_od.sh /builder/build.sh
RUN mkdir -p ./build && mkdir -p ./dist && \
    chmod +x /builder/build.sh && \
    bash /builder/build.sh

#RUN mkdir -p ./build && mkdir -p ./dist && \
#    uv run pyinstaller --clean --onedir --distpath ./dist --workpath ./build --specpath ./build \
#  --copy-metadata fastmcp \
#  --additional-hooks-dir=hooks \
#  --name geenii \
#  ./src/geenii/cli/main.py || exit 1

## build using nuitka
#RUN uv run pip install "patchelf==0.17.2.1" zstandard ordered-set
#RUN uv run python -m nuitka \
#    --include-package=geenii \
#    --include-package=mcp \
#    --include-package=fastmcp \
#    --include-distribution-metadata=fastmcp \
#    --standalone \
#    --onefile \
#    --output-filename=geenii \
#    --output-dir=dist \
#    ./src/geenii/cli/main.py

FROM python:3.14-alpine

# Install system dependencies
RUN apk add --no-cache \
    bash \
    curl \
    git \
    nodejs \
    npm \
    docker-cli \
    openssl \
    openssh-client \
    && rm -rf /var/cache/apk/* \
    && npm i -g pnpm

# Create non-root user and group, set permissions for geenii and home directory
RUN addgroup --gid 33311 -S geenii && adduser --uid 33311 -S geenii -G geenii && \
    mkdir -p /geenii && \
    chown -R geenii:geenii /geenii && \
    mkdir -p /home/geenii && \
    chown -R geenii:geenii /home/geenii

# Binaries
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
#COPY --from=builder /builder/dist/geenii /usr/bin/geenii
COPY --from=builder /builder/dist/geenii /opt/geenii
RUN chmod +x /opt/geenii/geenii && ln -sf /opt/geenii/geenii /usr/bin/geenii

COPY ./container/entrypoint.sh /usr/bin/entrypoint
RUN chmod +x /usr/bin/entrypoint
ENTRYPOINT ["/usr/bin/entrypoint"]

WORKDIR /workspace
USER geenii
CMD ["--help"]
