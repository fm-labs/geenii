#!/bin/bash

rm -rf ./build/
rm -rf ./dist/bin/
mkdir -p ./build
mkdir -p ./dist/bin

uv run pyinstaller --clean --onefile --distpath ./dist/bin --workpath ./build --specpath ./build \
  --name geenii \
  ./src/cli.py

uv run pyinstaller --clean --onefile --distpath ./dist/bin --workpath ./build --specpath ./build \
  --name geeniid \
  --copy-metadata fastmcp \
  --collect-submodules geenii.provider \
  ./src/server.py
