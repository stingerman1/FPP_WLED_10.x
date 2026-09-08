# Installation and lifecycle

## Prerequisites

Use a **64-bit stock FPP 10** image on Raspberry Pi 4 or 5. The installer rejects other architectures, models, FPP major versions and ABI fingerprints. It compiles against `/opt/fpp/src`; missing headers or incompatible libraries fail installation instead of downloading substitute FPP binaries. It does not patch FPP.

A 64-bit kernel (`uname -m` reporting `aarch64`) is not enough: Python, the compiler and installed `libfpp.so` must also be 64-bit AArch64. The installer checks these before changing state or compiling. A 32-bit userspace cannot be converted by reinstalling this plugin.

An administrator must provide `git`, `g++`, `python3`, `python3-venv`, timezone data (`tzdata`), `sudo`, `systemd` and JSONcpp development headers (`libjsoncpp-dev` on Debian). The installed FPP headers/library must match the running FPP version. Internet access is required for the pinned WLED source and Python dependencies. No sudo dependency installation is hidden inside the installer.

Clone to exactly `/home/fpp/media/plugins/FPP_WLED_10.x`, then run `sudo bash scripts/install.sh`. FPP's plugin install callback delegates to the same script. A pinned Linux-port checkout is retained under `.upstream/WLED-linux`; an altered rendering tree, different commit or divergent platform wrapper stops the build.

The installer stages an immutable runtime release, validates state and the plugin ABI, installs a supervised `fpp-wled.service`, checks its local status endpoint, and switches `build/current`. It retains `build/previous` for rollback. It does not automatically restart FPP or interrupt playback. **Install or upgrade between shows, then restart FPP from its UI.** The adapter loaded into an existing FPP process is not hot-replaced.

## FPP web access

The plugin opens `/fpp-wled/` and `/fpp-wled/settings` on FPP's existing browser origin, preserving its port and HTTP/HTTPS protocol. The installer enables a plugin-owned Apache configuration and gracefully reloads Apache after a configuration check. HTTP and WebSocket traffic use a separate authenticated Unix socket, `web.sock`; the trusted `control.sock` is never exposed. Stock FPP listeners and source files are unchanged. Removal disables this Apache configuration.

Port 8787 remains an optional direct runtime listener, bound to loopback on new installs. Existing bind/port settings are preserved and do not affect the FPP proxy. Do not change the runtime port to FPP's port: the runtime and Apache cannot share a TCP listener. Updating an existing installation requires rerunning the installer to enable the proxy. A rollback to a runtime predating web.sock needs direct runtime access again.

## First setup

1. Restart FPP. Open the plugin page, then its WLED setup link, normally `http://FPP-IP/fpp-wled/settings`.
2. Read `auth.json` as the `fpp` user from `/home/fpp/media/config/plugin.FPP_WLED_10.x`. Enter its token in setup. The HTTP cookie is HttpOnly/SameSite Strict; API clients use `Authorization: Bearer TOKEN`. HTTP is intended for the trusted show network; it does not provide transport encryption.
3. Edit the configuration JSON. `pixels` defines the virtual canvas, RGB (3) or RGBW (4). Virtual indexes are zero-based. FPP `channel` values are one-based. A mapping copies `count` pixels starting at `pixel` to a consecutive FPP channel range. Destination ranges must not overlap.
4. Configure actual outputs, native WLED channel destinations and channel ordering in FPP. For an FPP model, use its resolved channel range; automatic model-name resolution is not implemented.
5. Save configuration, then `sudo systemctl restart fpp-wled`. Configuration changes require a service restart. Confirm fresh observer status, the correct channel mapping and idle FPP before enabling ambient.

Example matrix mapping:

```json
{
  "version": 1, "port": 8787, "fps": 40,
  "pixels": {"count": 1024, "channels": 3, "width": 32, "height": 32},
  "mappings": [{"pixel": 0, "count": 1024, "channel": 3001}],
  "devices": []
}
```

Optional `ledmap` has one entry per logical pixel: each value is its physical virtual-pixel destination, or `-1` to omit it. Channel-range mappings are applied after this remap. Built-in bounds are safety ceilings, **not measured Pi throughput limits**: 16,000 pixels, 32 segments, 256 mappings, 64 devices and 60 fps.

## Native devices and optional integrations

Add devices to `devices`, for example `{"id":"porch","address":"192.0.2.10","mode":"effect","groups":["outside"]}`. Replace documentation addresses with your network addresses. Modes are `effect`, `sync` or `fpp-stream`. Enrolled IPs must be unique and must not also be listed as global UDP peers. Device HTTP uses port 80 and bounded timeouts; custom HTTP ports and credentials are not implemented.

- Set `"discovery":true` to browse `_wled._tcp.local.`; inspect `/api/discovery`, then manually enroll an IPv4 address.
- Set `"udp":{"enabled":true,"port":21324,"groups":1,"peers":["192.0.2.11"]}` for allowlisted WLED v12 notifier packets. `groups` is a bitmask. Network group settings must agree with the peer. Native `sync` devices may override `sync_port` and `sync_groups`.
- Set `"mqtt":{"enabled":true,"host":"broker.lan","port":1883,"id":"fpp_wled_house","topic":"wled/house","tls":false}`. Give each installation a unique ID/topic. Store optional credentials separately in `mqtt-secret.json`, with `username` and `password`, owned by fpp and mode 0600. Never put credentials in the public configuration API. Home Assistant MQTT light discovery is emitted automatically; this is not full parity with HA's native WLED integration.
- Timers use Linux local time: `"timers":[{"hour":18,"minute":0,"days":[0,1,2,3,4,5,6],"preset":1}]`. Monday is 0. Timers encountered during a show are skipped, not replayed. Use Linux Setup > Follow the daylight for solar timers, location/timezone, offsets and preview; saves there apply immediately. See [schedule semantics](CONTROL.md#clock-sunrise-and-sunset-schedules). The upstream ESP timer settings page remains unavailable.

## Upgrade, rollback, removal

Stop scheduled activity before lifecycle work. Record your installed Git commit and back up the configuration directory. Pull/review the desired plugin revision and run the installer again. Old state, saved presets, desired native commands and explicit show locks are retained. If validation fails before activation, the active release remains selected. A failed health check restores the previous release when one exists. Source builds pin inputs but are not claimed byte-for-byte reproducible across toolchains.

`sudo bash scripts/rollback.sh` checks the previous adapter's ABI, selects the previous immutable runtime and restarts the runtime service. Restart FPP afterward. Rollback does not roll back user settings; retain your backup for incompatible future schema changes.

`sudo bash scripts/fpp_uninstall.sh` stops/disables the runtime and removes its service configuration. Remove the plugin through FPP, then restart FPP to unload the adapter. User configuration and persistent show locks are deliberately retained outside the plugin directory. Delete them separately only if you intend to erase saved state.

## Diagnose

Use `systemctl status fpp-wled`, `journalctl -u fpp-wled`, `/api/status` and `python3 scripts/wledctl.py status`. A missing observer usually means FPP has not loaded the adapter, the service is starting, or the adapter failed. An ownership storage fault or invalid config fails closed. A persistent show source needs a matching Show End; restarting the plugin cannot clear it. Never clear an unknown lock merely to make lights turn on.
