#!/bin/bash

set -e

echo "Building tauri updater json from latest build ..."

TARGET_TRIPLE=$(rustc --print host-tuple)

APP_NAME="geenii-desktop"
VERSION=$(cat VERSION)
DOWNLOAD_BASE="https://geenii.flowmotion-labs.com/downloads/geenii"

json=$(jq -n '
{
  version: "",
  notes: "",
  pub_date: "",
  platforms: {}
}')

add_platform() {
  local json="$1"
  local platform="$2"
  local signature="$3"
  local url="$4"

  jq \
    --arg platform "$platform" \
    --arg signature "$signature" \
    --arg url "$url" \
    '.platforms[$platform] = {
        signature: $signature,
        url: $url
     }' <<< "$json"
}

add_pub_date() {
  local json="$1"
  #local pub_date=$(date -u +"%Y-%m-%dT%H:%M:%S%:Z")
  local pub_date=$(date -u +"%Y-%m-%dT%H:%M:%S.%N+00:00")

  jq \
    --arg pub_date "$pub_date" \
    '.pub_date = $pub_date' <<< "$json"
}

add_version() {
  local json="$1"
  local version="$2"

  jq \
    --arg version "$version" \
    '.version = $version' <<< "$json"
}

add_description() {
  local json="$1"
  local description="$2"

  jq \
    --arg description "$description" \
    '.notes = $description' <<< "$json"
}

echo "Detect signatures ..."

if [[ "$TARGET_TRIPLE" == *"aarch64-apple-darwin"* ]]; then
    SIG_FILE="./ui/src-tauri/target/release/bundle/macos/${APP_NAME}.app.tar.gz.sig"
    if [[ ! -f "$SIG_FILE" ]]; then
        echo "Signature file not found at $SIG_FILE. Please run build_desktop.sh first."
        exit 1
    fi
    json=$(add_pub_date "$json")
    json=$(add_version "$json" "$VERSION")
    json=$(add_description "$json" "Initial release of Geenii Desktop for macOS.")
    json=$(add_platform "$json" \
    "darwin-aarch64" \
    "$(cat $SIG_FILE)" \
    "${DOWNLOAD_BASE}/${VERSION}/macos/${APP_NAME}.app.tar.gz")

    # write to dist/updates.latest.json
    echo "Writing updates JSON to ./data/updater.latest.json ..."
    echo "$json" > ./data/updater.latest.json

    cat ./data/updater.latest.json

elif [[ "$TARGET_TRIPLE" == *x86_64-unknown-linux-gnu* ]]; then
    SIG_FILE="./ui/src-tauri/target/release/bundle/deb/${APP_NAME}_${VERSION}_amd64.deb.sig"
    if [[ ! -f "$SIG_FILE" ]]; then
        echo "Signature file not found at $SIG_FILE. Please run build_desktop.sh first."
        exit 1
    fi
    json=$(add_pub_date "$json")
    json=$(add_version "$json" "$VERSION")
    json=$(add_description "$json" "Initial release of Geenii Desktop for Debian-based systems.")
    json=$(add_platform "$json" \
    "x86_64-unknown-linux-gnu" \
    "$(cat $SIG_FILE)" \
    "${DOWNLOAD_BASE}/${VERSION}/deb/${APP_NAME}_${VERSION}_amd64.deb")

    # write to dist/updates.latest.json
    echo "Writing updates JSON to ./updates.latest.json ..."
    echo "$json" > ./updates.latest.json

    cat ./updates.latest.json


elif [[ "$TARGET_TRIPLE" == *"windows"* ]]; then
    # pass
    echo "Windows build not implemented yet. Skipping."
fi
