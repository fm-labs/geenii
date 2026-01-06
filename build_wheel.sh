#!/bin/bash

#rm -rf dist/
mkdir -p ./dist/
rm -f ./dist/*.whl

echo "Building wheel..."
uv build --wheel
