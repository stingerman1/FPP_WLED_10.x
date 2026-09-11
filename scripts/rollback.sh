#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ $EUID -eq 0 ]] || { echo 'Run rollback as root.' >&2; exit 1; }
. scripts/fpp-paths.sh
# Validate before stopping anything. Legacy snapshots without PHP pages cannot
# safely restore a matching UI; install a complete release before using rollback.
target="$(python3 scripts/releases.py validate build/previous)"
original="$(readlink -f build/current)"
python3 scripts/verify-abi.py "${FPPDIR}/src" build/previous/libFPP_WLED_10.x.so
(cd "$target"; runuser -u fpp -- python3 -m runtime.service --state-dir "$PLUGIN_STATE" --validate)
systemctl stop fpp-wled.service
restore() {
  ln -s "$original" build/current.restore
  mv -Tf build/current.restore build/current
  systemctl restart fpp-wled.service || true
  echo 'Rollback activation failed; original release restored.' >&2
}
trap restore ERR
ln -s "$target" build/current.rollback
mv -Tf build/current.rollback build/current
systemctl start fpp-wled.service
python3 scripts/check-health.py
ln -s build/current/libFPP_WLED_10.x.so libFPP_WLED_10.x.so.rollback
mv -Tf libFPP_WLED_10.x.so.rollback libFPP_WLED_10.x.so
ln -s "$original" build/previous.rollback
mv -Tf build/previous.rollback build/previous
trap - ERR
setSetting restartFlag 1
echo 'Prior local runtime restored. Restart FPP from the UI. Configuration and show locks were preserved.'
