#!/bin/bash

# Path or content of your private key
KEY_PATH="$HOME/.tauri/signing.key"
KEY_CONTENT=$(cat "$KEY_PATH")

export TAURI_SIGNING_PRIVATE_KEY="$KEY_CONTENT"
export TAURI_SIGNING_PRIVATE_KEY_PASSWORD=""

yarn tauri build