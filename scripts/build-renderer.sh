#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/prepare_renderer.py
g++ -std=gnu++17 -O2 -fPIC -shared -Ibuild/engine \
  build/engine/FX.cpp build/engine/FX_fcn.cpp build/engine/FX_2Dfcn.cpp \
  build/engine/colors.cpp build/engine/palettes.cpp build/engine/wled_math.cpp \
  build/engine/FXparticleSystem.cpp build/engine/fontmanager.cpp \
  build/engine/src/dependencies/fastled_slim/*.cpp \
  build/engine/platform.cpp build/engine/linux_util.cpp -Wl,--no-undefined -o build/libwled_linux.so.new
mv -f build/libwled_linux.so.new build/libwled_linux.so
