#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
plugin_dir="$(pwd -P)"
state_dir=/home/fpp/media/config/plugin.FPP_WLED_10.x
fpp_src=/opt/fpp/src
if [[ $EUID -ne 0 ]]; then echo 'Run this installer as root through FPP or sudo.' >&2; exit 1; fi
if [[ $(uname -m) != aarch64 ]]; then echo 'Installation requires Raspberry Pi 4/5 with 64-bit FPP.' >&2; exit 1; fi
model="$(tr -d '\0' </proc/device-tree/model)"
case "$model" in 'Raspberry Pi 4 '*|'Raspberry Pi 5 '*) ;; *) echo "Unsupported hardware: $model" >&2; exit 1;; esac
if [[ "$plugin_dir" != /home/fpp/media/plugins/FPP_WLED_10.x ]]; then
  echo 'Clone this repository into /home/fpp/media/plugins/FPP_WLED_10.x first.' >&2; exit 1
fi
for tool in git g++ objdump python3 systemctl apache2ctl a2enconf a2disconf; do command -v "$tool" >/dev/null; done
test -f "$fpp_src/Plugin.h"
python3 scripts/check-platform.py "$fpp_src"
# Do not install guessed FPP headers or modify stock FPP. Dependency installation
# remains an explicit administrator action if their image lacks the compiler.
install -d -o fpp -g fpp -m 0750 "$state_dir"
install -d -o fpp -g fpp -m 0770 /run/fpp-wled
# Repair a socket made by an older adapter already loaded in FPP. New adapters
# set these permissions themselves on every bind, including after a reboot.
if [[ -S /run/fpp-wled/frames.sock && ! -L /run/fpp-wled/frames.sock ]]; then
  chgrp fpp /run/fpp-wled/frames.sock
  chmod 0660 /run/fpp-wled/frames.sock
fi
printf 'd /run/fpp-wled 0770 fpp fpp -\n' >/etc/tmpfiles.d/fpp-wled.conf
if [[ ! -f "$state_dir/config.json" ]]; then
  install -o fpp -g fpp -m 0600 config.example.json "$state_dir/config.json"
fi
bash scripts/build-renderer.sh
bash scripts/build-plugin.sh
python3 scripts/verify-abi.py "$fpp_src" build/libFPP_WLED_10.x.so >build/abi.json
runuser -u fpp -- python3 -m runtime.service --state-dir "$state_dir" --validate
# Immutable release trees keep running Python code and dlopened libraries intact
# while a new version builds. A single symlink selects the next runtime release.
release="releases/$(date -u +%Y%m%dT%H%M%S)-$$"
mkdir -p "build/$release/build"
cp -a runtime web "build/$release/"
cp -a build/ui "build/$release/build/"
cp build/libwled_linux.so "build/$release/build/"
cp build/libFPP_WLED_10.x.so "build/$release/"
python3 -m venv "build/$release/.venv"
"build/$release/.venv/bin/pip" install --disable-pip-version-check --no-deps -r requirements.txt
if [[ -L build/current ]]; then
  ln -s "$(readlink build/current)" build/previous.new
  mv -Tf build/previous.new build/previous
fi
systemctl stop fpp-wled.service 2>/dev/null || true
ln -s "$release" build/current.new
mv -Tf build/current.new build/current
ln -s build/current/libFPP_WLED_10.x.so libFPP_WLED_10.x.so.new
mv -Tf libFPP_WLED_10.x.so.new libFPP_WLED_10.x.so
chmod 0755 callbacks.sh scripts/*.sh scripts/wledctl.py
install -m 0644 systemd/fpp-wled.service /etc/systemd/system/fpp-wled.service
systemctl daemon-reload
systemctl enable fpp-wled.service
if ! { systemctl restart fpp-wled.service && python3 scripts/check-health.py && bash scripts/configure-web.sh; }; then
  if [[ -L build/previous ]]; then
    ln -s "$(readlink build/previous)" build/current.restore
    mv -Tf build/current.restore build/current
    systemctl restart fpp-wled.service
  fi
  echo 'Activation failed; restored previous release when available.' >&2
  exit 1
fi
echo 'Installed alpha. Restart FPP from its UI to load/rebuild the adapter. Ambient starts disabled.'
echo 'User state and show locks are preserved. A missing Show End must be cleared by its source ID.'
