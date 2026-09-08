#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ $EUID -eq 0 ]] || { echo 'Run web configuration as root.' >&2; exit 1; }
target=/etc/apache2/conf-available/fpp-wled.conf
enabled=/etc/apache2/conf-enabled/fpp-wled.conf
backup=$(mktemp)
had_config=0
was_enabled=0
[[ ! -f "$target" ]] || { cp "$target" "$backup"; had_config=1; }
[[ ! -e "$enabled" ]] || was_enabled=1
restore() {
    if [[ $had_config == 1 ]]; then cp "$backup" "$target"; else rm -f "$target"; fi
    if [[ $was_enabled == 1 ]]; then a2enconf fpp-wled >/dev/null; else a2disconf fpp-wled >/dev/null; fi
}
trap 'rm -f "$backup"' EXIT
if [[ ${1:-} == --remove ]]; then
    a2disconf fpp-wled >/dev/null
else
    install -m 0644 apache/fpp-wled.conf "$target"
    a2enconf fpp-wled >/dev/null
fi
if ! apache2ctl configtest || ! systemctl reload apache2; then
    restore
    echo 'Apache configuration failed; previous plugin web configuration restored.' >&2
    exit 1
fi
if [[ ${1:-} == --remove ]]; then rm -f "$target"; fi
