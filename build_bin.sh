#!/bin/bash

rm -rf ./build/
rm -rf ./dist/
mkdir -p ./build
mkdir -p ./dist/

uv run pyinstaller --clean --onefile --distpath ./dist --workpath ./build --specpath ./build \
  --copy-metadata fastmcp \
  --name geenii \
  ./src/cli.py || exit 1
