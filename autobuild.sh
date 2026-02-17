#!/bin/bash

# check if there are any outstanding changes locally
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "You have uncommitted changes. Please commit or stash them before running this script."
    exit 1
fi

echo "Starting auto-build script. This will check for updates every 5 minutes and rebuild if there are changes."
echo "Press Ctrl+C to stop the script."
sleep 5

# main loop
while true; do

  now=$(date +"%Y-%m-%d %H:%M:%S")
  echo "Checking for updates at $now..."

  # fetch remote updates
  git fetch --quiet

  # compare local and remote commits
  LOCAL=$(git rev-parse @)
  REMOTE=$(git rev-parse @{u})
  if [ "$LOCAL" != "$REMOTE" ]; then
      echo "New changes detected, rebuilding..."

      # WARNING: destroys local changes
      #git reset --hard @{u}
      #git clean -fd

      if ! bash build_desktop.sh --skip-build-binaries ; then
          echo "Build failed !!!"
      fi
  else
      echo "Already up to date"
  fi

  # wait for 5 minutes
  sleep 300
done