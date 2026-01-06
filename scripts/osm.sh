#!/bin/bash

set -x

X=46
Y=17
Z=5

TILE_DATA_DIR="data/osm/tiles"
TILE_NAME="tile_${Z}_${X}_${Y}.png"
TILE_URL="https://tile.openstreetmap.org/${Z}/${X}/${Y}.png"

mkdir -p "${TILE_DATA_DIR}"
curl -o "${TILE_NAME}" "${TILE_URL}" \
  -H "Accept: image/png" \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3" \
  -H "Referer: https://www.openstreetmap.org/"
