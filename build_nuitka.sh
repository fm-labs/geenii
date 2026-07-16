#!/bin/bash

rm -rf dist/
mkdir -p dist

if [[ $1 = "--onefile" ]]; then

  uv run python -m nuitka \
    --include-package=geenii \
    --include-package=mcp \
    --include-package=fastmcp \
    --include-distribution-metadata=fastmcp \
    --standalone \
    --onefile \
    --output-filename=geenii \
    --output-dir=dist \
    ./src/geenii/cli/main.py || exit 1

else

  uv run python -m nuitka \
    --include-package=geenii \
    --include-package=mcp \
    --include-package=fastmcp \
    --include-distribution-metadata=fastmcp \
    --standalone \
    --output-filename=geenii \
    --output-dir=dist \
    ./src/geenii/cli/main.py || exit 1
fi


