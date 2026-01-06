# This scripts builds whispercpp Docker image with the latest code.

SD_SRC_DIR=data/src/whispercpp

WD=$(pwd)

# exit trap
trap "cd $WD ; exit" INT TERM ERR

# checkout repo
if [ ! -d "$SD_SRC_DIR" ]; then
  git clone https://github.com/ggml-org/whisper.cpp.git "$SD_SRC_DIR"
fi

cd "$SD_SRC_DIR" || exit 1

# update repo
git pull origin master

docker build -t whispercpp:latest -f .devops/main.Dockerfile .
