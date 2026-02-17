#!/bin/bash

mkdir -p ./build
rm -rf ./build/
#mkdir -p ./dist/bin
#rm -rf ./dist/bin

BUILD_DIST_DIR=${BUILD_DIST_DIR:-./dist/bin}
mkdir -p "$BUILD_DIST_DIR"

TARGET_TRIPLE=$(rustc --print host-tuple)

uv sync --frozen

uv run pyinstaller --clean --onefile --distpath $BUILD_DIST_DIR --workpath ./build --specpath ./build \
  --name geenii-${TARGET_TRIPLE} \
  ./src/cli.py

uv run pyinstaller --clean --onefile --distpath $BUILD_DIST_DIR --workpath ./build --specpath ./build \
  --name geeniid-${TARGET_TRIPLE} \
  --copy-metadata fastmcp \
  --collect-submodules geenii.provider \
  ./src/server.py
