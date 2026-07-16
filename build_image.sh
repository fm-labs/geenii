#!/bin/bash

TAG_NAME="geenii:latest"
time docker build -f ./Dockerfile -t $TAG_NAME --progress plain .
