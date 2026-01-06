
print_usage() {
  echo "Usage: $0 <command> <prompt> [<input_image>]"
  echo "Available commands:"
  echo "  txt2img"
  echo "  txtfile2img"
  echo "  img2img"
  echo "Example: $0 txt2img 'cat with blue eyes'"
  echo "Example: $0 txtfile2img ./prompts.txt"
  echo "Example: $0 img2img 'cat with blue eyes' input_image.png"
}

IMAGE=stable-diffusion:latest
CMD=$1
if [ -z "$CMD" ]; then
  print_usage
  exit 1
fi
shift

PROMPT=$1
if [ -z "$PROMPT" ]; then
  print_usage
  exit 1
fi
shift

# Check if the image is available
if ! docker image inspect $IMAGE >/dev/null 2>&1; then
  echo "Image $IMAGE not found, building..."
  bash ./sd_build.sh
else
  echo "Image $IMAGE already exists."
fi

# Create output directory
mkdir -p "$(pwd)/data/sd"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_IMAGE="${TIMESTAMP}_${CMD}_output.png"
STOP=0

# trap to handle Ctrl+C
trap 'echo "Stopping..."; STOP=1; exit 0' SIGINT SIGTERM

if [ "$CMD" == "txt2img" ]; then
  echo "Running Stable Diffusion txt2img..."

  time docker run --rm \
    -v "$(pwd)/data/models:/models" \
    -v "$(pwd)/data/sd:/data" \
    $IMAGE \
    sd -m /models/sd-v1-4.ckpt -p "${PROMPT}" -o /data/${OUTPUT_IMAGE} --strength 0.4

  echo "Output saved to /data/${OUTPUT_IMAGE}"

elif [ "$CMD" == "txtfile2img" ]; then
  INPUT_FILE=$PROMPT
  if [ -z "$INPUT_FILE" ]; then
    echo "Input file is required for txtfile2img command."
    print_usage
    exit 1
  fi
  if [ ! -f "$INPUT_FILE" ]; then
    echo "Input file not found: $INPUT_FILE"
    exit 1
  fi

  # read line by line from input file
  while IFS= read -r line; do
      # skip empty lines
      if [ -z "$line" ]; then
        continue
      fi
      # skip lines starting with #
      if [[ "$line" == \#* ]]; then
        continue  # skip comments
      fi
      # check for stop signal
      if [ $STOP -eq 1 ]; then
        echo "Stopping processing due to signal."
        break
      fi

      TIMESTAMP=$(date +%Y%m%d_%H%M%S)
      OUTPUT_IMAGE="${TIMESTAMP}_txt2img_output.png"
      echo "${OUTPUT_IMAGE}: txt2img: $line"
      time docker run --rm \
        -v "$(pwd)/data/models:/models" \
        -v "$(pwd)/data/sd:/data" \
        $IMAGE \
        sd -m /models/sd-v1-4.ckpt -p "${line}" -o /data/${OUTPUT_IMAGE} --strength 0.4

      echo "Output saved to /data/${OUTPUT_IMAGE}"
  done < "$INPUT_FILE"

elif [ "$CMD" == "img2img" ]; then
  echo "Running Stable Diffusion img2img..."
  INPUT_IMAGE=$1
  if [ -z "$INPUT_IMAGE" ]; then
    echo "Input image is required for img2img command."
    print_usage
    exit 1
  fi
  if [ ! -f "/data/${INPUT_IMAGE}" ]; then
    echo "Input image not found: /data/${INPUT_IMAGE}"
    exit 1
  fi

  time docker run --rm \
    -v "$(pwd)/data/models:/models" \
    -v "$(pwd)/data/sd:/data" \
    $IMAGE \
    sd -m /models/sd-v1-4.ckpt -p "${PROMPT}" -i /data/${INPUT_IMAGE} -o /data/${OUTPUT_IMAGE} --strength 0.4

  echo "Output saved to /data/${OUTPUT_IMAGE}"
else
  echo "Unknown command: $CMD"
  print_usage
  exit 1
fi
