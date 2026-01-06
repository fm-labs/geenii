#!/bin/bash

# Set all cache locations
export HF_HOME="$PWD/data/huggingface"
export TRANSFORMERS_CACHE="$PWD/data/huggingface/transformers"
export HF_HUB_CACHE="$PWD/data/huggingface/hub"

mkdir -p "$HF_HOME" "$TRANSFORMERS_CACHE" "$HF_HUB_CACHE"

if [ $# -gt 0 ]; then
    # Use command line arguments
    input="$*"
elif [ ! -t 0 ]; then
    # Read from stdin
    input=$(cat)
else
    echo "Usage: echo 'text' | $0  OR  $0 'text'"
    exit 1
fi

# Read all stdin content
#input=$(cat)
echo "Input: $input"

uv run xtts.py "$input"