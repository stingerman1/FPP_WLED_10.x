# Installation and lifecycle

## Prerequisites

Use a **64-bit stock FPP 10** image on Raspberry Pi 4 or 5. The installer rejects other architectures, models, FPP major versions and ABI fingerprints. It compiles against `/opt/fpp/src`; missing headers or incompatible libraries fail installation instead of downloading substitute FPP binaries. It does not patch FPP.

A 64-bit kernel (`uname -m` reporting `aarch64`) is not enough: Python, the compiler and installed `libfpp.so` must also be 64-bit AArch64. The installer checks these before changing state or compiling. A 32-bit userspace cannot be converted by reinstalling this plugin.

An administrator must provide `git`, `g++`, `objdump` (binutils), `python3`, `python3-venv`, timezone data (`tzdata`), `sudo`, `systemd` and JSONcpp development headers (`libjsoncpp-dev` on Debian). The installed FPP headers/library must match the running FPP version. Internet access is required for the pinned WLED source and Python dependencies. No sudo dependency installation is hidden inside the installer.

Clone to exactly `/home/fpp/media/plugins/FPP_WLED_10.x`, then run `sudo bash scripts/install.sh`. FPP's plugin install callback delegates to the same script. A pinned Linux-port checkout is retained under `.upstream/WLED-linux`; an altered rendering tree, different commit or divergent platform wrapper stops the build.

ABI verification reads the compiled constant fingerprints from the installed library and candidate with objdump, without loading daemon-dependent libraries into Python. Unrecognized code or mismatched fingerprints fail closed. FPP performs final symbol resolution and its ABI checks when it loads the adapter.

The installer stages an immutable release of PHP pages, web assets, runtime and adapter, validates state and the plugin ABI, installs a supervised `fpp-wled.service`, checks its local status endpoint, and switches `build/current`. It retains `build/previous` for rollback. It does not automatically restart FPP or interrupt playback. **Install or upgrade between shows, then restart FPP from its UI.** The adapter loaded into an existing FPP process is not hot-replaced.

## FPP web access

The plugin opens `/fpp-wled/` and `/fpp-wled/settings` on FPP's existing browser origin, preserving its port and HTTP/HTTPS protocol. The installer enables a plugin-owned Apache configuration and gracefully reloads Apache after a configuration check. HTTP and WebSocket traffic use a separate authenticated Unix socket, `web.sock`; the trusted `control.sock` is never exposed. Stock FPP listeners and source files are unchanged. Removal disables this Apache configuration.

Port 8787 remains an optional direct runtime listener, bound to loopback on new installs. Existing bind/port settings are preserved and do not affect the FPP proxy. Do not change the runtime port to FPP's port: the runtime and Apache cannot share a TCP listener. Updating an existing installation requires rerunning the installer to enable the proxy. Rollback requires a complete release snapshot with versioned PHP pages; legacy snapshots are rejected before the running service is stopped.

## First setup

1. Restart FPP. Open the plugin page, then its WLED setup link, normally `http://FPP-IP/fpp-wled/settings`.
2. Open WLED and choose **Enable lighting controls**, either on the main screen or in **Settings > Runtime access**. The explanation beside the button describes its permission to change lighting, presets and configuration. FPP retrieves its existing token and saves browser access in one action; no copy/paste or SSH is needed. Access is remembered for one year and renewed by access checks. **Forget access on this browser** removes it; another browser/address needs its own authorization. External API clients can retrieve the token under **Advanced: retrieve a token for an API client** on the FPP plugin page and use `Authorization: Bearer TOKEN`. Direct runtime access offers manual token entry in Settings. Anyone with FPP web access can authorize controls, so limit it to trusted users. The HttpOnly/SameSite Strict cookie avoids JavaScript storage; HTTP still requires a trusted show network.
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

- Use **Settings → Discovery & synchronization** to discover and advertise instances and configure automatic peers without a restart. See [discovery and sync setup](DISCOVERY_SYNC.md).
- Set `"udp":{"enabled":true,"port":21324,"groups":1,"peers":["192.0.2.11"]}` for allowlisted WLED v12 notifier packets. `groups` is a bitmask. Network group settings must agree with the peer. Native `sync` devices may override `sync_port` and `sync_groups`.
- Set `"mqtt":{"enabled":true,"host":"broker.lan","port":1883,"id":"fpp_wled_house","topic":"wled/house","tls":false}`. Give each installation a unique ID/topic. Store optional credentials separately in `mqtt-secret.json`, with `username` and `password`, owned by fpp and mode 0600. Never put credentials in the public configuration API. Home Assistant MQTT light discovery is emitted automatically; this is not full parity with HA's native WLED integration.
- Timers use Linux local time: `"timers":[{"hour":18,"minute":0,"days":[0,1,2,3,4,5,6],"preset":1}]`. Monday is 0. Timers encountered during a show are skipped, not replayed. Use Linux Setup > Follow the daylight for solar timers, location/timezone, offsets and preview; saves there apply immediately. See [schedule semantics](CONTROL.md#clock-sunrise-and-sunset-schedules). The upstream ESP timer settings page remains unavailable.

## Upgrade, rollback, removal

Stop scheduled activity before lifecycle work. Record your installed Git commit and back up the configuration directory. Pull/review the desired plugin revision and run the installer again. Old state, saved presets, desired native commands and explicit show locks are retained. If validation fails before activation, the active release remains selected. A failed health check restores the previous release when one exists. Source builds pin inputs but are not claimed byte-for-byte reproducible across toolchains.

`sudo bash scripts/rollback.sh` checks the previous release, adapter ABI and settings compatibility before stopping the runtime. It switches PHP pages and runtime assets together, checks runtime health, and restores the original release if activation fails. Restart FPP afterward. Saved configuration and show locks are preserved. Snapshots from before versioned PHP pages are not eligible: complete another successful update first. Keep a settings backup for future incompatible schema changes.

Updates retain the current and previous releases, plus releases referenced by live processes (including an adapter still mapped into FPP). Unused older snapshots are pruned. If process references cannot be inspected, pruning is deferred. The installer checks free space before building. Removal attempts independent cleanup even if Apache fails, reports incomplete steps, and preserves data by default.

`sudo bash scripts/fpp_uninstall.sh` stops/disables the runtime and removes its service configuration. Remove the plugin through FPP, then restart FPP to unload the adapter. User configuration and persistent show locks are deliberately retained outside the plugin directory. Delete them separately only if you intend to erase saved state.

## Diagnose

Use `systemctl status fpp-wled`, `journalctl -u fpp-wled`, `/api/status` and `python3 scripts/wledctl.py status`. A missing observer usually means FPP has not loaded the adapter, the service is starting, or the adapter failed. An ownership storage fault or invalid config fails closed. A persistent show source needs a matching Show End; restarting the plugin cannot clear it. Never clear an unknown lock merely to make lights turn on.

## FPP lifecycle integration

Install resolves media and log paths through FPP common. Existing directory-based settings migrate intact into `plugindata/FPP_WLED_10.x`; the standard `config/plugin.FPP_WLED_10.x` file holds the data-directory registration and removal preference. The service uses system Python and declared pip dependencies. Runtime diagnostics append to `plugin-FPP_WLED_10.x.log` in FPP logs; FPP handles rotation.

The root Makefile includes FPP shared setup and rebuilds the adapter during FPP core upgrades. Installation and rollback request an FPP restart through its flag, never restart fppd directly. Until that restart, a loaded adapter may remain the previous version.

Uninstall removes service, Apache and temporary runtime artifacts. Saved data is retained by default. On the plugin page, enable **Delete saved data when uninstalling** before uninstalling only if you want permanent removal of tokens, presets and ownership locks. This preference is off by default. The FPP-managed diagnostic log is retained for support.

Use **Outputs & devices** for guided pixel layout, channel mappings and device enrollment. Save, then use **Apply saved setup: restart WLED runtime** when FPP ownership is clear. The pending indicator distinguishes saved changes from active settings. The supervised restart pauses ambient output briefly and preserves saved state; it does not restart FPP.
