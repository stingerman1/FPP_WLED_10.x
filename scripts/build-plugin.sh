#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
fpp_src="${FPP_SRC:-/opt/fpp/src}"
test -f "$fpp_src/Plugin.h" || { echo 'Installed FPP development headers are required.' >&2; exit 1; }
exec make SRCDIR="$fpp_src" build/libFPP_WLED_10.x.so
