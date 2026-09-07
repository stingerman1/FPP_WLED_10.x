#!/bin/bash
# FPP queries this script to locate the pre-overlay C++ plugin.
if [ "${1:-}" = "--list" ]; then
  echo 'c++:libFPP_WLED_10.x.so'
fi
