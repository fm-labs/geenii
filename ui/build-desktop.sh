#!/bin/bash

# https://tauri.app/distribute/
# https://tauri.app/plugin/updater/

# Path or content of your private key
KEY_PATH="$HOME/.tauri/signing.key"
KEY_CONTENT=$(cat "$KEY_PATH")

TAURI_SIGNING_PRIVATE_KEY="$KEY_CONTENT" \
TAURI_SIGNING_PRIVATE_KEY_PASSWORD="" \
exec pnpm tauri build "$@"
