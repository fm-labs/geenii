#!/bin/bash
set -xe
#rm -rf dist/
mkdir -p ./dist/
rm -f ./dist/*.whl

echo "Building wheel..."
uv build --wheel