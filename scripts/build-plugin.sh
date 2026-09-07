#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
fpp_src="${FPP_SRC:-/opt/fpp/src}"
test -f "$fpp_src/Plugin.h" || { echo 'Installed FPP development headers are required.' >&2; exit 1; }
mkdir -p build
g++ -std=c++20 -O2 -Wall -Wextra -Wno-unused-parameter -fPIC -shared -pthread \
  -I"$fpp_src" plugin/plugin.cpp -L"$fpp_src" -Wl,-rpath,"$fpp_src" -lfpp \
  -o build/libFPP_WLED_10.x.so.new
mv -f build/libFPP_WLED_10.x.so.new build/libFPP_WLED_10.x.so
