#!/bin/bash

rm -rf ./build/
rm -rf ./dist/
mkdir -p ./build
mkdir -p ./dist/

uv run pyinstaller --clean --onedir --distpath ./dist --workpath ./build --specpath ./build \
  --copy-metadata fastmcp \
  --additional-hooks-dir=hooks \
  --name geenii \
  ./src/geenii/cli/main.py || exit 1
