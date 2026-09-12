#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
bash scripts/build-renderer.sh
g++ -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined -g tests/frame_test.cpp -o build/frame-test
ASAN_OPTIONS=detect_leaks=1 build/frame-test
g++ -std=c++17 -Wall -Wextra -Werror -pthread -fsanitize=address,undefined -g tests/worker_test.cpp -o build/worker-test
ASAN_OPTIONS=detect_leaks=1 build/worker-test
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m compileall -q runtime scripts tests
for script in callbacks.sh scripts/*.sh; do bash -n "$script"; done
