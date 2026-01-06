#!/bin/bash

AUDIOSDIR=$PWD/data/audios
MODELDIR=$PWD/data/models
mkdir -p $MODELDIR

#IMAGE=ghcr.io/ggml-org/whisper.cpp:main-e7bf0294ec9099b5fc21f5ba969805dfb2108cea@sha256:516d466a45cb788f128dd2a050d5c25904d46561ce061a468203571ce8280a16
#IMAGE=ghcr.io/ggml-org/whisper.cpp:main
IMAGE=whispercpp:latest

PLATFORM=linux/arm64

if ! docker image inspect $IMAGE >/dev/null 2>&1; then
  echo "Image $IMAGE not found, building..."
  bash ./whisper_build.sh
else
  echo "Image $IMAGE already exists."
fi

#docker run -it --rm \
#  -v $MODELDIR:/models \
#  $IMAGE "./models/download-ggml-model.sh base /models"

## transcribe an audio file
#docker run -it --rm \
#  -v $MODELDIR:/models \
#  -v $AUDIOSDIR:/audios \
#  $IMAGE "whisper-cli -m /models/ggml-base.bin -f /audios/samples_jfk.wav"

uv run xwhisper.py
