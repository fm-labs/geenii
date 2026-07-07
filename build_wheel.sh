#!/bin/bash
set -xe
#rm -rf dist/
mkdir -p ./dist/
rm -f ./dist/*.whl

echo "Building wheel..."
uv build --wheel

if [[ $1 == "--copy" ]] ; then
   cp -f ./dist/geenii-0.3.1-py3-none-any.whl ../geeniid/libs/
fi