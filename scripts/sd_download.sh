# This scripts downloads the Stable Diffusion models from Hugging Face.

# curl -L -O https://huggingface.co/CompVis/stable-diffusion-v-1-4-original/resolve/main/sd-v1-4.ckpt
## curl -L -O https://huggingface.co/CompVis/stable-diffusion-v-1-4-original/resolve/main/sd-v1-4-full-ema.ckpt
## curl -L -O https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors
## curl -L -O https://huggingface.co/stabilityai/stable-diffusion-2-1/resolve/main/v2-1_768-nonema-pruned.safetensors
## curl -L -O https://huggingface.co/stabilityai/stable-diffusion-3-medium/resolve/main/sd3_medium_incl_clips_t5xxlfp16.safetensors

MODEL_DIR=data/models
MODEL=$1
if [ -z "$MODEL" ]; then
  echo "Usage: $0 <model_name>"
  echo "  Available models:"
  echo "    sd-v1-4"
  echo "    sd-v1-4-full-ema"
  echo "    sd-v1-5"
  echo "    sd-v2-1"
  echo "    sd-3-medium"
  exit 1
fi

# Download the model if it does not exist
mkdir -p "$MODEL_DIR"

case "$MODEL" in
  sd-v1-4)
    MODEL_URL="https://huggingface.co/CompVis/stable-diffusion-v-1-4-original/resolve/main/sd-v1-4.ckpt"
    ;;
  sd-v1-5)
    MODEL_URL="https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors"
    ;;
  sd-v2-1)
    MODEL_URL="https://huggingface.co/stabilityai/stable-diffusion-2-1/resolve/main/v2-1_768-nonema-pruned.safetensors"
    ;;
  sd-3-medium)
    MODEL_URL="https://huggingface.co/stabilityai/stable-diffusion-3-medium/resolve/main/sd3_medium_incl_clips_t5xxlfp16.safetensors"
    ;;
  *)
    # if the model starts with "http", treat it as a direct URL
    if [[ "$MODEL" == http* ]]; then
      MODEL_URL="$MODEL"
    else
      echo "Unknown model: $MODEL"
      exit 1
    fi
    ;;
esac

# Check if the model file already exists
MODEL_FILE="$MODEL_DIR/$(basename "$MODEL_URL")"
if [ ! -f "$MODEL_FILE" ]; then
  echo "Downloading model: $MODEL"
  curl -L -o "$MODEL_FILE" "$MODEL_URL"
else
  echo "Model already exists: $MODEL_FILE"
fi
