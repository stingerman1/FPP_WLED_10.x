# Alpha compatibility matrix

This matrix describes current `main`. The `v0.1.0-alpha.1` release predates the preset/playlist compatibility expansion described below.

Current main also provides a native WLED preset-file importer in Linux Setup: previewed translations, per-entry errors, forward playlist references, catalog conflict detection, and atomic merge. See [import instructions](CONTROL.md#importing-native-wled-presets). Unsupported effects and non-default hardware features remain explicit incompatibilities; import does not synthesize replacements.

Pinned WLED: v16.0.1 (`29b389df1c1aaec6ff53aea742d17063b985906c`). Reference FPP headers: v10.0 branch commit `370e62ed7e8c8318da6ee5b01312b8b75082d952`. Installed FPP 10 ABI 6 is checked during installation. Other FPP majors are rejected. No Pi/FPP combination is yet hardware certified.

| Capability | Current implementation / limitation |
|---|---|
| Effects | Actual upstream rendering code, 129 strip / 171 matrix IDs; unsupported slots keep their IDs and are marked unavailable. Tested for bounded execution, not visually certified effect by effect. |
| Palettes | Built-in palettes and paginated `/json/palx` previews; native-format custom gradients in slots 0–128 (IDs 200 down to 72), converted through upstream FastLED. Linux Setup provides JSON/file import, editing, export, preview and protected deletion. Usermod palettes remain excluded. |
| Segments | Up to 32, selected-segment updates, colors, brightness, grouping/spacing/offset, reverse/mirror, 2D transforms, mapping options, custom sliders and options. Deleting segments compacts IDs. |
| RGB/RGBW and 2D | Virtual RGB(W) canvas, dimensions and explicit ledmap; FPP owns physical bus types and ordering. No CCT bus or hardware current limiting. |
| Transitions | Upstream ordinary transitions/mode blending compiled; custom transition styles are unavailable. |
| Presets | JSON IDs 1–250, `ib/sb/sc` selective saves, UTF-8 quick-load labels, bounded snapshots and partial custom JSON (`o:true`). Lighting-only `win` command presets and bounded numeric preset cycling are supported; see CONTROL.md. Harmless stock-export defaults translate to Linux. Unsupported non-default fields reject with 422. Boot-preset overrides, reference chains, random expressions and general HTTP commands remain unavailable. |
| Playlists | Sequential or shuffled entries (`r:true` or negative repeat), scalar/short-array durations, indefinite entries (`dur:0`), next-entry requests (`np:true`), repeat/end and return-to-prior-preset (`end:255`). Shuffle order and interrupted entry persist across takeover and restart. Nested playlists remain unavailable. |
| Timers | Linux local weekday/hour/minute/preset schedules. No sunrise/sunset, nightlight or upstream settings-page parity. |
| UI | Upstream main WLED UI and Linux setup/status/palette editor. Firmware update, provisioning, upstream configuration pages, pixel peek and arbitrary file editors unavailable. |
| HTTP/JSON | State/info/effects/fxdata/palettes/presets and plugin APIs. Authenticated mutations, explicit unsupported-field errors. Legacy `/win`, arbitrary filesystem and full `/json/cfg` parity unavailable. |
| WebSocket | State/info updates and authenticated supported JSON mutations. Not a complete upstream websocket implementation; fragmented requests unavailable. |
| UDP | WLED notifier v12, group mask and explicit peer allowlist; local geometry preserved on receive. Experimental; no native-hardware interoperability result yet. |
| MQTT / Home Assistant | Paho MQTT, JSON commands and basic brightness/on/off, MQTT light discovery. No full native HA WLED integration certification. |
| Native devices | mDNS suggestions, manual IPv4 enrollment, per-device/group HTTP effects/presets or UDP sync; bounded queues/timeouts and realtime safeguard. UDP cannot select a preset by ID. |
| Pixel streaming | Via FPP-configured DDP/E1.31/Art-Net outputs, using mapped channels. No independent runtime pixel sender. |
| Show arbitration | FPP playlist/sequence/live detection plus persistent source locks; tested with synthetic FPP heartbeat/IPC. Stock FPP and physical routing acceptance pending. |
| Restore | Local runtime selection/on/off preserved; local ambient playlist restarts its interrupted entry. Native effect mode captures lighting settings, persists checkpoints, checks identity and retries after realtime ends. Saved native playlists restart from the beginning; their cursor, remaining repeats, effect phase, unsaved playlists and active nightlights are not recoverable here. Sync mode and effect mode without a current checkpoint retain last-command fallback. |
| ESP features | Flashing, Wi-Fi provisioning, ESP-NOW, GPIO peripherals, audio input, usermods and Philips Hue excluded. |
| Other exclusions | File fonts (embedded fonts remain), device firmware configuration, arbitrary file uploads, OTA, native-device authentication and arbitrary user extensions. Palette and preset JSON imports are supported. |

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

Remaining software features such as legacy command parsing, nightlight modes, nested playlists and fragmented WebSockets can be implemented through additional adapters. ESP-NOW, physical GPIO and audio input need explicit Linux hardware/network backends; they cannot become equivalent by accepting their configuration fields alone. Physical routing guarantees still require hardware acceptance.

Native checkpoint recovery uses the pinned upstream JSON state/info fields and `pd` preset-direct semantics. Native WLED's regular state API exposes `ps` and `pl`, but does not expose the playlist cursor or remaining repetitions. Re-selecting a saved playlist restores its selection with a fresh run; it does not reconstruct its interrupted entry. Snapshot capture is best effort: automatic shows use the last ambient poll, while an explicit Show Start from allowed ambient requests a fresh capture before returning. A failed capture retains the previous checkpoint and reports the failure. See [native recovery details](CONTROL.md#native-device-recovery).

Custom palette files accept 2–18 complete stops: flat index/R/G/B groups or index/hex pairs. Positions must be ordered, begin at 0 and terminate at 255. Eight-digit hex colors discard white, matching upstream RGB palettes. Unlike native permissive/truncating parsing, malformed or oversized input is rejected. Gaps retain gray placeholders through the highest saved slot, preserving IDs; absent slots cannot be selected or imported in presets. The registry does not use native filesystem gap-scanning limits. Palette previews use the same upstream gradient conversion as rendering. Native devices retain their own palette files; this API does not distribute custom palettes to them.
