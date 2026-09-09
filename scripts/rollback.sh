#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ $EUID -eq 0 ]] || { echo 'Run rollback as root.' >&2; exit 1; }
. scripts/fpp-paths.sh
test -f build/previous/build/libwled_linux.so
test -f build/previous/libFPP_WLED_10.x.so
python3 scripts/verify-abi.py "${FPPDIR}/src" build/previous/libFPP_WLED_10.x.so
systemctl stop fpp-wled.service
ln -s "$(readlink build/previous)" build/current.rollback
mv -Tf build/current.rollback build/current
systemctl start fpp-wled.service
ln -s build/current/libFPP_WLED_10.x.so libFPP_WLED_10.x.so.rollback
mv -Tf libFPP_WLED_10.x.so.rollback libFPP_WLED_10.x.so
setSetting restartFlag 1
echo 'Prior local runtime restored. Restart FPP from the UI. Configuration and show locks were preserved.'
