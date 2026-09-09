#!/bin/bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run removal as root through FPP.' >&2; exit 1; }
. "$(dirname "$0")/fpp-paths.sh"
bash "$(dirname "$0")/configure-web.sh" --remove
systemctl disable --now fpp-wled.service || true
rm -f /etc/systemd/system/fpp-wled.service /etc/tmpfiles.d/fpp-wled.conf
systemctl daemon-reload
if [[ -d /run/fpp-wled && ! -L /run/fpp-wled ]]; then
  rm -f /run/fpp-wled/control.sock /run/fpp-wled/web.sock /run/fpp-wled/observer.sock /run/fpp-wled/frames.sock /run/fpp-wled/runtime.lock
  rmdir /run/fpp-wled 2>/dev/null || true
fi
setSetting restartFlag 1
if [[ $(php "$(dirname "$0")/register-settings.php" purge-requested) == 1 ]]; then
  python3 "$(dirname "$0")/purge-data.py" "$MEDIADIR"
  echo 'Opted-in removal: saved plugin data deleted.'
else
  echo 'Runtime stopped; user configuration, presets and persistent show locks retained as requested.'
fi
echo 'Restart FPP after removing the plugin to unload its adapter.'
