#!/bin/bash

# https://tauri.app/distribute/
# https://tauri.app/plugin/updater/

set -xe

WD=$(pwd)
SIDECAR_BIN_DIR="./ui/src-tauri/binaries"
#TARGET_TRIPLE=$(rustc --print host-tuple)

# Path or content of your private key
KEY_PATH="$HOME/.tauri/signing.key"
KEY_CONTENT=$(cat "$KEY_PATH")

echo "Building sidecar binaries for desktop platforms..."
export BUILD_DIST_DIR="$SIDECAR_BIN_DIR"
source ./build_bin.sh


#echo "Copying sidecar binaries ..."
## copy to src-tauri/binaries with target triple in name
#mkdir -p ./ui/src-tauri/binaries
#if [[ "$TARGET_TRIPLE" == *"apple-darwin"* ]]; then
#    BIN_FILE="./dist/bin/geeniid"
#    if [[ ! -f "$BIN_FILE" ]]; then
#        echo "Binary not found at $BIN_FILE. Please run build_bin.sh first."
#        exit 1
#    fi
#    cp -f "$BIN_FILE" "./ui/src-tauri/binaries/geeniid-${TARGET_TRIPLE}"
#
#elif [[ "$TARGET_TRIPLE" == *"unknown-linux-gnu"* ]]; then
#    BIN_FILE="./dist/bin/geeniid"
#    if [[ ! -f "$BIN_FILE" ]]; then
#        echo "Binary not found at $BIN_FILE. Please run build_bin.sh first."
#        exit 1
#    fi
#    cp -f "$BIN_FILE" "./ui/src-tauri/binaries/geeniid-${TARGET_TRIPLE}"
#
#elif [[ "$TARGET_TRIPLE" == *"windows"* ]]; then
#    BIN_FILE="./dist/bin/geeniid.exe"
#    echo "Not implemented yet. Skipping."
#    exit 1
#fi

cd ./ui
pnpm install --frozen-lockfile
#if ! pnpm run build ; then
#    echo "UI build failed. Exiting."
#    cd ..
#    exit 1
#fi

set +x
export TAURI_SIGNING_PRIVATE_KEY="$KEY_CONTENT"
export TAURI_SIGNING_PRIVATE_KEY_PASSWORD=""
set -x
if ! pnpm tauri build ; then
    echo "Tauri build failed. Exiting."
    cd ..
    exit 1
fi

cd "$WD"
source ./build_updates_json.sh

echo "Build completed successfully."
exit 0
