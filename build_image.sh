#!/bin/bash

TAG_NAME="geenii:latest"
docker build -f ./Dockerfile -t $TAG_NAME --progress plain .
