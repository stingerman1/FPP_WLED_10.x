# Local validation — 2026-09-07

- Linux x86-64 under Ubuntu 24.04 / WSL2: actual WLED renderer compiled and linked with no undefined symbols.
- Plugin suite: all 25 tests passed in the final combined run with the pinned Linux-port checkout and optional dependencies installed.
- All 129 strip-supported and 171 matrix-supported effect IDs rendered bounded frames; separate exact RGBW, distinct-segment mapping and fresh-process deterministic Rainbow checks passed. These do not certify all effects visually or exhaustively.
- C++ frame parser/copy checks passed with AddressSanitizer and UndefinedBehaviorSanitizer.
- FPP adapter compiled against the pinned stock FPP10 reference headers. No installed FPP daemon/library or Pi hardware was available, so ABI load and playback acceptance remain open.
- Browser: the real upstream UI loaded without console errors after integration fixes, authenticated through Linux setup, and selecting Rainbow changed `/json/state` to `fx:9`. Desktop screenshot inspected locally. Automated API regressions cover the UI's partial colors, selected segments and `fxdef` payloads.
- Standalone `ports/fpp-linux` build passed. Upstream `npm test` passed 16 tests; `pio run -e esp32dev` compiled successfully (101.8 seconds; 81,536 RAM / 1,298,125 flash bytes). This was a compile regression check; no ESP device was flashed. Initial Windows test runs exposed timestamp/concurrent-build sensitivity; the isolated final run passed and the original firmware tree remained unchanged.
- The upstream npm dependency install reported one high-severity advisory in its existing development dependency tree. Those npm packages are not installed by the Linux plugin installer; upstream tooling dependency review remains outstanding.

[desktop-benchmark.json](desktop-benchmark.json) records 400 measured frames after warmup for each workload. The 1,000-pixel Rainbow run averaged 0.0207 ms renderer time; 32×32 Spaceships averaged 0.0274 ms. These are desktop renderer-only measurements, not real-time output latency or supported Pi limits. Use the hardware campaign in [ACCEPTANCE.md](ACCEPTANCE.md) before claiming show reliability or Pi throughput.
