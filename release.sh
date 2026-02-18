#!/bin/bash

set -ex

APP_NAME="geenii-desktop"
APP_VERSION=$(cat ./VERSION)
TARGET_TRIPLE=$(rustc --print host-tuple)

SCP_BIN=$(which scp)

[[ -f .env.local ]] && source .env.local

SSH_USER=${DEPLOY_SSH_USER:?"Environment variable DEPLOY_SSH_USER is not set"}
SSH_HOST=${DEPLOY_SSH_HOST:?"Environment variable DEPLOY_SSH_HOST is not set"}
SSH_PORT=${DEPLOY_SSH_PORT:-22}  # Default to port 22 if not set
SSH_KEY_PATH=${DEPLOY_SSH_KEY_PATH:?"Environment variable DEPLOY_SSH_KEY_PATH is not set"}
SSH_REMOTE_DIR="web/geenii/releases/${APP_NAME}/${APP_VERSION}/${TARGET_TRIPLE}"  # Remote directory to upload files to

RELEASE_API_URL="https://geenii.flowmotion-labs.com/release.php"
RELEASE_API_AUTH_USER=${RELEASE_API_AUTH_USER:-}
RELEASE_API_AUTH_PASS=${RELEASE_API_AUTH_PASS:-}


function upload_ssh() {
    local local_path="$1"
    local remote_path="$2"

    echo "Uploading $local_path -> $SSH_USER@$SSH_HOST:${SSH_REMOTE_DIR}$remote_path"
    # -s = Force SFTP subsystem
    $SCP_BIN -s -o ConnectTimeout=10 -i "$SSH_KEY_PATH" -P "$SSH_PORT" "$local_path" "$SSH_USER@$SSH_HOST:${SSH_REMOTE_DIR}$remote_path"
}


# function to submit release info to API
function submit_release_info() {
    local platform=$1
    local bundle=$2
    local filename=$3

    local api_url=${RELEASE_API_URL:?"Environment variable RELEASE_API_URL is not set"}
    local api_auth_user=${RELEASE_API_AUTH_USER:?"Environment variable RELEASE_API_AUTH_USER is not set"}
    local api_auth_pass=${RELEASE_API_AUTH_PASS:?"Environment variable RELEASE_API_AUTH_PASS is not set"}
    #local api_headers=$(printf "-H 'Authorization: Basic %s' " "$(echo -n "$api_auth_user:$api_auth_pass" | base64)")

    local payload=$(jq -n \
        --arg name "$APP_NAME" \
        --arg version "$APP_VERSION" \
        --arg bundle "$bundle" \
        --arg filename "$filename" \
        --arg platform "$platform" \
        '{
            "name": $name,
            "version": $version,
            "platform": $platform,
            "bundle": $bundle,
            "filename": $filename
        }')

    echo "Submitting release info to API: $payload"
    if curl -X POST \
        -H "Content-Type: application/json" \
        -H "Authorization: Basic $(echo -n "$api_auth_user:$api_auth_pass" | base64)" \
        -d "$payload" \
        "$api_url?action=submit" | jq -e '.success == true' > /dev/null; then
      echo "Release info submitted successfully."
    else
      echo "Failed to submit release info."
    fi
}

if [[ "$1" == "--help" ]]; then
    echo "Usage: $0"
    echo "This script uploads the built application bundles to the server and submits release info to the API."
    exit 0
fi


# MacOS ARM bundles
if [[ "$TARGET_TRIPLE" == *"aarch64-apple-darwin"* ]]; then
    # dmg
    if [[ -d "./ui/src-tauri/target/release/bundle/dmg/" ]]; then
      upload_ssh "./ui/src-tauri/target/release/bundle/dmg/${APP_NAME}_${APP_VERSION}_aarch64.dmg" "/dmg/${APP_NAME}_aarch64.dmg" && \
      submit_release_info $TARGET_TRIPLE "dmg" "${APP_NAME}_aarch64.dmg"
    fi
    # macos app
    if [[ -d "./ui/src-tauri/target/release/bundle/macos/" ]]; then
      upload_ssh "./ui/src-tauri/target/release/bundle/macos/${APP_NAME}.app.tar.gz" "/app/${APP_NAME}.app.tar.gz" && \
      upload_ssh "./ui/src-tauri/target/release/bundle/macos/${APP_NAME}.app.tar.gz.sig" "/app/${APP_NAME}.app.tar.gz.sig" && \
      submit_release_info $TARGET_TRIPLE "app" "${APP_NAME}.app.tar.gz"
    fi
# MacOS AMD64 bundles
elif [[ "$TARGET_TRIPLE" == *"x86_64-apple-darwin"* ]]; then
    # dmg
    if [[ -d "./ui/src-tauri/target/release/bundle/dmg/" ]]; then
      upload_ssh "./ui/src-tauri/target/release/bundle/dmg/${APP_NAME}_${APP_VERSION}_x86_64.dmg" "/dmg/${APP_NAME}_x86_64.dmg" && \
      submit_release_info $TARGET_TRIPLE "dmg" "${APP_NAME}_x86_64.dmg"
    fi
    # macos app
    if [[ -d "./ui/src-tauri/target/release/bundle/macos/" ]]; then
      upload_ssh "./ui/src-tauri/target/release/bundle/macos/${APP_NAME}.app.tar.gz" "/app/${APP_NAME}.app.tar.gz" && \
      upload_ssh "./ui/src-tauri/target/release/bundle/macos/${APP_NAME}.app.tar.gz.sig" "/app/${APP_NAME}.app.tar.gz.sig" && \
      submit_release_info $TARGET_TRIPLE "app" "${APP_NAME}.app.tar.gz"
    fi
# Linux ARM64
elif [[ "$TARGET_TRIPLE" == *"aarch64-unknown-linux"* ]]; then
    # deb
    if [[ -d "./ui/src-tauri/target/release/bundle/deb/" ]]; then
      upload_ssh "./ui/src-tauri/target/release/bundle/deb/${APP_NAME}_${APP_VERSION}_arm64.deb" "/deb/${APP_NAME}_${APP_VERSION}_arm64.deb" && \
      upload_ssh "./ui/src-tauri/target/release/bundle/deb/${APP_NAME}_${APP_VERSION}_arm64.deb.sig" "/deb/${APP_NAME}_${APP_VERSION}_arm64.deb.sig" && \
      submit_release_info $TARGET_TRIPLE "deb" "${APP_NAME}_${APP_VERSION}_arm64.deb"
    fi
    # rpm
    if [[ -d "./ui/src-tauri/target/release/bundle/rpm/" ]]; then
      upload_ssh "./ui/src-tauri/target/release/bundle/rpm/${APP_NAME}-${APP_VERSION}-1.aarch64.rpm" "/rpm/${APP_NAME}-${APP_VERSION}-1.aarch64.rpm" && \
      upload_ssh "./ui/src-tauri/target/release/bundle/rpm/${APP_NAME}-${APP_VERSION}-1.aarch64.rpm.sig" "/rpm/${APP_NAME}-${APP_VERSION}-1.aarch64.rpm.sig" && \
      submit_release_info $TARGET_TRIPLE "rpm" "${APP_NAME}-${APP_VERSION}-1.aarch64.rpm"
    fi
    # appimage
    if [[ -d "./ui/src-tauri/target/release/bundle/appimage/" ]]; then
      upload_ssh "./ui/src-tauri/target/release/bundle/appimage/${APP_NAME}_${APP_VERSION}_arm64.AppImage" "/appimage/${APP_NAME}_${APP_VERSION}_arm64.AppImage" && \
      upload_ssh "./ui/src-tauri/target/release/bundle/appimage/${APP_NAME}_${APP_VERSION}_arm64.AppImage.sig" "/appimage/${APP_NAME}_${APP_VERSION}_arm64.AppImage.sig" && \
      submit_release_info $TARGET_TRIPLE "appimage" "${APP_NAME}_${APP_VERSION}_arm64.AppImage"
    fi
# Linux AMD64
elif [[ "$TARGET_TRIPLE" == *"x86_64-unknown-linux"* ]]; then
    # deb
    if [[ -d "./ui/src-tauri/target/release/bundle/deb/" ]]; then
      upload_ssh "./ui/src-tauri/target/release/bundle/deb/${APP_NAME}_${APP_VERSION}_amd64.deb" "/deb/${APP_NAME}_${APP_VERSION}_amd64.deb" && \
      upload_ssh "./ui/src-tauri/target/release/bundle/deb/${APP_NAME}_${APP_VERSION}_amd64.deb.sig" "/deb/${APP_NAME}_${APP_VERSION}_amd64.deb.sig" && \
      submit_release_info $TARGET_TRIPLE "deb" "${APP_NAME}_${APP_VERSION}_amd64.deb"
    fi
    # rpm
    if [[ -d "./ui/src-tauri/target/release/bundle/rpm/" ]]; then
      upload_ssh "./ui/src-tauri/target/release/bundle/rpm/${APP_NAME}-${APP_VERSION}-1.x86_64.rpm" "/rpm/${APP_NAME}-${APP_VERSION}-1.x86_64.rpm" && \
      upload_ssh "./ui/src-tauri/target/release/bundle/rpm/${APP_NAME}-${APP_VERSION}-1.x86_64.rpm.sig" "/rpm/${APP_NAME}-${APP_VERSION}-1.x86_64.rpm.sig" && \
      submit_release_info $TARGET_TRIPLE "rpm" "${APP_NAME}-${APP_VERSION}-1.x86_64.rpm"
    fi
    # appimage
    if [[ -d "./ui/src-tauri/target/release/bundle/appimage/" ]]; then
      upload_ssh "./ui/src-tauri/target/release/bundle/appimage/${APP_NAME}_${APP_VERSION}_amd64.AppImage" "/appimage/${APP_NAME}_${APP_VERSION}_amd64.AppImage" && \
      upload_ssh "./ui/src-tauri/target/release/bundle/appimage/${APP_NAME}_${APP_VERSION}_amd64.AppImage.sig" "/appimage/${APP_NAME}_${APP_VERSION}_amd64.AppImage.sig" && \
      submit_release_info $TARGET_TRIPLE "appimage" "${APP_NAME}_${APP_VERSION}_amd64.AppImage"
    fi
else
    echo "Release for target triple $TARGET_TRIPLE is not implemented yet. Skipping."
fi
