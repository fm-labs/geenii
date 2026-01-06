# This scripts builds stable-diffusion docker image with the latest code.

SD_SRC_DIR=data/src/sd
MODEL_DIR=data/models/sd

WD=$(pwd)

# exit trap
trap "cd $WD ; exit" INT TERM ERR

# checkout sd
if [ ! -d "$SD_SRC_DIR" ]; then
  git clone --recursive https://github.com/leejet/stable-diffusion.cpp "$SD_SRC_DIR"
fi

cd "$SD_SRC_DIR" || exit 1

# update sd
git pull origin master
git submodule update --init --recursive --merge

docker build -t stable-diffusion:latest -f Dockerfile .


# build sd
#mkdir -p build
#cd build || exit 1
#cmake ..

# Using OpenBLAS for CPU acceleration
#cmake .. -DGGML_OPENBLAS=ON
# Using CUDA for NVIDIA GPUs
#cmake .. -DSD_CUDA=ON
# Using HipBLAS for AMD GPUs
#cmake .. -G "Ninja" -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DSD_HIPBLAS=ON -DCMAKE_BUILD_TYPE=Release -DAMDGPU_TARGETS=gfx1100
# Using MUSA
#cmake .. -DCMAKE_C_COMPILER=/usr/local/musa/bin/clang -DCMAKE_CXX_COMPILER=/usr/local/musa/bin/clang++ -DSD_MUSA=ON -DCMAKE_BUILD_TYPE=Release
# Using Metal
#cmake .. -DSD_METAL=ON
# Using Vulkan
#cmake .. -DSD_VULKAN=ON