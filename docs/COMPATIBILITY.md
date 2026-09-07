# Alpha compatibility matrix

Pinned WLED: v16.0.1 (`29b389df1c1aaec6ff53aea742d17063b985906c`). Reference FPP headers: v10.0 branch commit `370e62ed7e8c8318da6ee5b01312b8b75082d952`. Installed FPP 10 ABI 6 is checked during installation. Other FPP majors are rejected. No Pi/FPP combination is yet hardware certified.

| Capability | Current implementation / limitation |
|---|---|
| Effects | Actual upstream rendering code, 129 strip / 171 matrix IDs; unsupported slots keep their IDs and are marked unavailable. Tested for bounded execution, not visually certified effect by effect. |
| Palettes | Built-in palette table; custom palettes and palette preview/editor API unavailable. |
| Segments | Up to 32, selected-segment updates, colors, brightness, grouping/spacing/offset, reverse/mirror, 2D transforms, mapping options, custom sliders and options. Deleting segments compacts IDs. |
| RGB/RGBW and 2D | Virtual RGB(W) canvas, dimensions and explicit ledmap; FPP owns physical bus types and ordering. No CCT bus or hardware current limiting. |
| Transitions | Upstream ordinary transitions/mode blending compiled; custom transition styles are unavailable. |
| Presets | JSON IDs 1–250; supported state fields preserve upstream formats. Unsupported fields reject with 422. UI save currently stores full supported state regardless of `ib/sb/sc` selection flags. Quick-load labels and preset HTTP command strings unavailable. |
| Playlists | Sequential preset IDs, durations, transitions, repeat/end; restart interrupted entry after takeover and process restart. Random ordering and nested playlists unavailable. |
| Timers | Linux local weekday/hour/minute/preset schedules. No sunrise/sunset, nightlight or upstream settings-page parity. |
| UI | Upstream main WLED UI, Linux setup/status page. Firmware update, provisioning, upstream configuration pages, pixel peek and file/palette editors unavailable. |
| HTTP/JSON | State/info/effects/fxdata/palettes/presets and plugin APIs. Authenticated mutations, explicit unsupported-field errors. Legacy `/win`, arbitrary filesystem and full `/json/cfg` parity unavailable. |
| WebSocket | State/info updates and authenticated supported JSON mutations. Not a complete upstream websocket implementation; fragmented requests unavailable. |
| UDP | WLED notifier v12, group mask and explicit peer allowlist; local geometry preserved on receive. Experimental; no native-hardware interoperability result yet. |
| MQTT / Home Assistant | Paho MQTT, JSON commands and basic brightness/on/off, MQTT light discovery. No full native HA WLED integration certification. |
| Native devices | mDNS suggestions, manual IPv4 enrollment, per-device/group HTTP effects/presets or UDP sync; bounded queues/timeouts and realtime safeguard. UDP cannot select a preset by ID. |
| Pixel streaming | Via FPP-configured DDP/E1.31/Art-Net outputs, using mapped channels. No independent runtime pixel sender. |
| Show arbitration | FPP playlist/sequence/live detection plus persistent source locks; tested with synthetic FPP heartbeat/IPC. Stock FPP and physical routing acceptance pending. |
| Restore | Runtime selection/on/off preserved; ambient playlist restarts interrupted entry. Native resume reissues the last desired command; complete native pre-show snapshot/playlist position restoration is not implemented. |
| ESP features | Flashing, Wi-Fi provisioning, ESP-NOW, GPIO peripherals, audio input, usermods and Philips Hue excluded. |
| Other exclusions | File fonts (embedded fonts remain), custom palettes, device firmware configuration, file uploads, OTA, native-device authentication and arbitrary user extensions. |

Control-mode exclusivity covers this plugin's configured senders. It cannot discover every external controller. Native effects already running on a device are not forcibly turned off by Show Start; the show must take realtime ownership of that target. Native `live` checks are a safeguard, not a replacement for hooks. Automatic detection cannot recall a command already in flight; successful explicit Show Start waits for prior native requests and adapter revocation. Mixed-routing hardware tests are required before claiming guaranteed end-to-end handoff.

Unknown/stale FPP observation disables the plugin's ambient contribution, but cannot stop unrelated direct-to-device software or autonomously running native effects. These limits mean the full project plan is **not yet complete**.
