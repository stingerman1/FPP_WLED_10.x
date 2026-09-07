# Alpha compatibility matrix

This matrix describes current `main`. The `v0.1.0-alpha.1` release predates the preset/playlist compatibility expansion described below.

Pinned WLED: v16.0.1 (`29b389df1c1aaec6ff53aea742d17063b985906c`). Reference FPP headers: v10.0 branch commit `370e62ed7e8c8318da6ee5b01312b8b75082d952`. Installed FPP 10 ABI 6 is checked during installation. Other FPP majors are rejected. No Pi/FPP combination is yet hardware certified.

| Capability | Current implementation / limitation |
|---|---|
| Effects | Actual upstream rendering code, 129 strip / 171 matrix IDs; unsupported slots keep their IDs and are marked unavailable. Tested for bounded execution, not visually certified effect by effect. |
| Palettes | Built-in palette table; custom palettes and palette preview/editor API unavailable. |
| Segments | Up to 32, selected-segment updates, colors, brightness, grouping/spacing/offset, reverse/mirror, 2D transforms, mapping options, custom sliders and options. Deleting segments compacts IDs. |
| RGB/RGBW and 2D | Virtual RGB(W) canvas, dimensions and explicit ledmap; FPP owns physical bus types and ordering. No CCT bus or hardware current limiting. |
| Transitions | Upstream ordinary transitions/mode blending compiled; custom transition styles are unavailable. |
| Presets | JSON IDs 1–250, `ib/sb/sc` selective saves, UTF-8 quick-load labels, bounded snapshots and partial custom JSON (`o:true`). Harmless stock-export defaults translate to Linux. Unsupported non-default fields reject with 422. Boot-preset overrides, preset references/cycling expressions and preset HTTP command strings remain unavailable. |
| Playlists | Sequential or shuffled entries (`r:true` or negative repeat), scalar/short-array durations, indefinite entries (`dur:0`), next-entry requests (`np:true`), repeat/end and return-to-prior-preset (`end:255`). Shuffle order and interrupted entry persist across takeover and restart. Nested playlists remain unavailable. |
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

## Translation rules

The implementation follows the pinned upstream [preset serialization](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/presets.cpp), [JSON state serialization](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/json.cpp) and [playlist behavior](https://github.com/wled/WLED/blob/29b389df1c1aaec6ff53aea742d17063b985906c/wled00/playlist.cpp).

- `ib:false` omits global power, brightness and transition from the saved preset. `sb:false` omits segment start/stop geometry. `sc:true` saves selected segment IDs only. Defaults remain full-state saves for older plugin clients that omit flags. A bounded all-segment snapshot disables segments added after saving it.
- `o:true` saves a validated partial JSON patch rather than expanding it into the current state. Missing fields take their values from the state at recall. Saved preset editing is still allowed during shows; recalling or advancing remains blocked.
- `ql` accepts up to eight UTF-8 bytes, matching upstream's quick-load buffer. Labels and names reject HTML markup characters because upstream renders them into HTML.
- Default-only fields translate without changing output: root `bs:0`, `ledmap:0`, and segment `cct:127`, `set:0`, `si:0`, `bm:0`. These do not enable advanced blending, CCT, sound input or other ledmap IDs. Non-default values are rejected rather than silently discarded.
- Short duration/transition arrays repeat their final value, as upstream does. Duration zero holds until `np:true`. Negative repeat means infinite shuffle; finite positive repeat counts full passes. Shuffle moves preset, duration and transition together. Exact random order is not intended to match an ESP's RNG.
- `end:255` captures the previously selected preset ID, not an arbitrary live-state snapshot. If no prior saved preset exists, the playlist stays on its last entry. Timer progress pauses while off; show suspension restarts the interrupted entry according to the plugin's handoff policy. Transition values remain limited to 65.5 seconds.

Remaining software features such as palette storage/editing, legacy command parsing, nightlight modes, nested playlists and fragmented WebSockets can be implemented through additional adapters. ESP-NOW, physical GPIO and audio input need explicit Linux hardware/network backends; they cannot become equivalent by accepting their configuration fields alone. Physical routing guarantees still require hardware acceptance.
