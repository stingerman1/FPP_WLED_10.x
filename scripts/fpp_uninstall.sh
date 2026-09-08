#!/bin/bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run removal as root through FPP.' >&2; exit 1; }
bash "$(dirname "$0")/configure-web.sh" --remove
systemctl disable --now fpp-wled.service || true
rm -f /etc/systemd/system/fpp-wled.service /etc/tmpfiles.d/fpp-wled.conf
systemctl daemon-reload
echo 'Runtime stopped; user configuration, presets and persistent show locks retained.'
echo 'Restart FPP after removing the plugin to unload its adapter.'
