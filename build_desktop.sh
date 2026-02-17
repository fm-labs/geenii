#!/bin/bash

# https://tauri.app/distribute/
# https://tauri.app/plugin/updater/

set -xe

WD=$(pwd)
SIDECAR_BIN_DIR="./ui/src-tauri/binaries"
TARGET_TRIPLE=$(rustc --print host-tuple)

# Trap to ensure we return to the original directory on exit
trap "cd $WD" EXIT


# Path or content of your private key
KEY_PATH="$HOME/.tauri/signing.key"
KEY_CONTENT=$(cat "$KEY_PATH")

SKIP_BUILD_BINARIES=0
if [[ "$1" == "--skip-build-binaries" ]]; then
    SKIP_BUILD_BINARIES=1
    shift
fi

if [[ $SKIP_BUILD_BINARIES -eq 0 ]]; then
    echo "Cleaning previous sidecar binaries..."
    rm -rf "$SIDECAR_BIN_DIR"
    mkdir -p "$SIDECAR_BIN_DIR"
    echo "Building sidecar binaries for desktop platforms..."
    export BUILD_DIST_DIR="$SIDECAR_BIN_DIR"
    source ./build_bin.sh
fi


cd ./ui
pnpm install --frozen-lockfile || exit 1

BUILD_ARGS=""
if [[ "$TARGET_TRIPLE" == *"aarch64-unknown-linux"* ]]; then
    BUILD_ARGS="--bundles deb,rpm"

elif [[ "$TARGET_TRIPLE" == *"darwin"* ]]; then
    BUILD_ARGS="--bundles app,dmg"

elif [[ "$TARGET_TRIPLE" == *"windows"* ]]; then
    BUILD_ARGS="--bundles exe"
fi

set +x
export TAURI_SIGNING_PRIVATE_KEY="$KEY_CONTENT"
export TAURI_SIGNING_PRIVATE_KEY_PASSWORD=""
set -x
if ! pnpm tauri build $BUILD_ARGS ; then
    echo "Tauri build failed. Exiting."
    cd ..
    exit 1
fi

cd "$WD"

echo "Build completed successfully."
exit 0
