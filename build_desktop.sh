#!/bin/bash

# https://tauri.app/distribute/
# https://tauri.app/plugin/updater/

set -xe

WD=$(pwd)
SIDECAR_BIN_DIR="./ui/src-tauri/binaries"
TARGET_TRIPLE=$(rustc --print host-tuple)

# Path or content of your private key
KEY_PATH="$HOME/.tauri/signing.key"
KEY_CONTENT=$(cat "$KEY_PATH")

echo "Building sidecar binaries for desktop platforms..."
export BUILD_DIST_DIR="$SIDECAR_BIN_DIR"
source ./build_bin.sh


cd ./ui
pnpm install --frozen-lockfile || exit 1

BUILD_ARGS=""
if [[ "$TARGET_TRIPLE" == *"aarch64-unknown-linux"* ]]; then
    BUILD_ARGS="--bundle deb,rpm"

elif [[ "$TARGET_TRIPLE" == *"darwin"* ]]; then
    BUILD_ARGS="--bundle app,dmg"

elif [[ "$TARGET_TRIPLE" == *"windows"* ]]; then
    BUILD_ARGS="--bundle exe"
fi

set +x
export TAURI_SIGNING_PRIVATE_KEY="$KEY_CONTENT"
export TAURI_SIGNING_PRIVATE_KEY_PASSWORD=""
set -x
if ! pnpm tauri build "$BUILD_ARGS" ; then
    echo "Tauri build failed. Exiting."
    cd ..
    exit 1
fi

cd "$WD"

echo "Build completed successfully."
exit 0
