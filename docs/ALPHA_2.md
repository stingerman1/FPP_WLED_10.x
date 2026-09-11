# Alpha 2 implementation and acceptance status

## Added

- **Virtual segments:** join ordered pixel ranges from named FPP strings or channel models; reverse individual ranges; arrange each segment as a strip or rectangular matrix. Preview and stage the whole replacement layout, then Apply setup. Saved editor definitions reload while source definitions match. Pixel numbering in the editor starts at 1. Matrix source pixels are selected in logical row-major order.
- **MQTT/Home Assistant setup:** broker address, port, TLS, topic, unique ID and protected credentials. Credentials are never returned by the API or included in backups. The existing MQTT integration publishes Home Assistant discovery; this is not certification of HA's native WLED integration.
- **Visual palettes:** edit two to eighteen color stops, inspect a gradient and save directly to the selected custom-palette slot. Existing palette reference and show-ownership guards still apply.
- **Setup backup/restore:** authenticated JSON download of active configuration, lighting state, presets, palette files, timers and explicit show locks. Preview validates the candidate in a separate renderer process. Restore is staged, cancellable and applied under the runtime lock at startup. A journal replays an interrupted restore before output starts. A pre-restore backup is downloadable.
- **WebSocket continuation messages:** bounded text-message assembly with interleaved ping support; authentication and ownership apply to completed commands. Invalid continuation order and oversized messages are rejected.
- **UI:** native FPP form styling for the new editors, named unavailable effects, and links explaining unavailable main-screen tools. Existing live summary, single-action buttons and return-to-FPP navigation remain.
- **Live settings synchronization:** untouched lighting fields follow external WLED state changes, including palette and all three RGBW colors. Draft fields are preserved until applied or discarded. The summary separately shows configured color controls and sampled rendered colors, including effect/palette output.

## Backup behavior

Backups contain the **active** setup, not unapplied configuration drafts. Restore
replaces the included files, unions existing and backed-up explicit show locks,
and leaves ambient disabled. Enable background lighting after reviewing outputs
and clearing only locks whose shows have actually ended. Browser access and MQTT
credentials remain on the destination player. FPP output configuration is outside
the plugin backup. Native-device recovery snapshots are cleared to avoid replaying
settings for a former routing setup. Nightlights do not restart after restoration.
The file limit is 8 MiB. Do not edit configuration while a restore is staged;
Apply setup will use the restored configuration.

## Virtual layout limits

One physical pixel can appear once in the composed layout. Overlapping models
and strings are rejected. Include every pixel that should receive ambient output;
unselected pixels are not contributed by this plugin. RGB and RGBW sources cannot
share one canvas. Custom/3D FPP model import and grouped hardware strings remain
unsupported without a suitable channel model. The canvas is limited to 16,000
pixels, 32 segments, 256 output ranges and 255 pixels per matrix axis. Combined
matrix/string shapes must fit that canvas. Existing presets using old geometry
may need editing after any layout replacement.

## Verification

Automated checks cover mapping order, reversal, matrix wiring, overlap rejection,
input persistence, broker-secret handling, visual palette save, backup download /
preview / staging, restore replay after interruption, show-lock preservation,
fragmented WebSocket authentication, and the existing settings workflows.
Browser tests mutate only disposable local fixture data. The new guided workflow
script is `tests/browser_remaining_workflows.js`; use a fixture MEDIADIR with two
named ten-pixel FPP strings (IDs 0 and 1). Source releases include both committed
plugin source and its pinned Linux WLED source, plus SHA-256 checksums.

## Still required before a stable release

1. Physical FPP-to-native-device streaming, UDP synchronization, show takeover,
   playlist gaps/pauses, overlapping locks and ambient restoration, including
   network loss, device restarts and missing Show End hooks.
2. Sustained Pi 4 and Pi 5 strip and representative matrix benchmarks. The earlier
   1,000-pixel Pi 4 sample near 40 fps is a short operational observation.
3. Safari/iOS, screen-reader and keyboard-only acceptance; cross-tab conflicts,
   long-running playlists and extended browser stability.
4. Remaining effects and native API differences: full `/json/cfg`, legacy `/win`
   route parity, advanced playlist behaviors and hardware-dependent functions.
   Supported lighting expressions in JSON `win` are only a bounded subset.
5. Pi binary release assets and FPP plugin-catalog submission after hardware
   acceptance. Catalog inclusion requires upstream acceptance.

FPP04 had no saved importable FPP channel models or pixel strings at the last
inspection. Its physical output configuration must be established before the
mapping and show tests can prove real light delivery. No live output remapping,
broker enrollment or restore is performed merely by installing this release.
