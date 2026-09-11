#!/bin/bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run removal as root through FPP.' >&2; exit 1; }
. "$(dirname "$0")/fpp-paths.sh"
failed=0
attempt() {
  if ! "$@"; then
    echo "Removal step failed: $*" >&2
    failed=1
  fi
}
# Removing a missing unit is harmless; a present unit must actually stop.
stopped=1
if [[ -f /etc/systemd/system/fpp-wled.service ]]; then
  if ! systemctl disable --now fpp-wled.service; then
    failed=1
    stopped=0
    echo 'Could not stop WLED; retaining its unit, sockets and saved data for retry.' >&2
  fi
fi
attempt bash "$(dirname "$0")/configure-web.sh" --remove
if (( stopped )); then attempt rm -f /etc/systemd/system/fpp-wled.service /etc/tmpfiles.d/fpp-wled.conf; fi
attempt systemctl daemon-reload
if (( stopped )) && [[ -d /run/fpp-wled && ! -L /run/fpp-wled ]]; then
  attempt rm -f /run/fpp-wled/control.sock /run/fpp-wled/web.sock /run/fpp-wled/observer.sock /run/fpp-wled/frames.sock /run/fpp-wled/runtime.lock
  rmdir /run/fpp-wled 2>/dev/null || true
fi
attempt setSetting restartFlag 1
purge_requested=0
if ! purge_requested=$(php "$(dirname "$0")/register-settings.php" purge-requested); then failed=1; fi
if (( stopped )) && [[ "$purge_requested" == 1 ]]; then
  attempt python3 "$(dirname "$0")/purge-data.py" "$MEDIADIR"
  echo 'Opted-in removal: saved plugin data deleted.'
else
  echo 'User configuration, presets and persistent show locks retained.'
fi
echo 'Restart FPP after removing the plugin to unload its adapter.'
if (( failed )); then echo 'Removal was incomplete. Review the failed steps above and retry removal.' >&2; fi
exit "$failed"
