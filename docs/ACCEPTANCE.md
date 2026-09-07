# Release acceptance record

Status: **alpha implementation; hardware acceptance open**. Do not publish production-ready claims or submit catalog metadata as validated until the relevant rows have evidence.

| Area | Current evidence | Remaining acceptance |
|---|---|---|
| Linux renderer | Compiled pinned upstream effects on x86-64 Linux/WSL; automated supported-effect, RGBW, mapping and deterministic-frame tests | Native Pi4/Pi5 runs, visual comparison to ESP WLED, long-term memory/thermal soak |
| FPP adapter | Reference FPP10 header compilation; sanitized frame parser tests | Load/ABI validation on stock image, real pre-overlay frame delivery, output timing and no show regressions |
| Ownership | Automated overlapping locks, quiet periods, pause/live flags, stale observer, persistence and real daemon/Unix-IPC fixture | Scheduled playlists, standalone/remote sequences, live input, black packets, gaps, pauses and repeated handoffs on FPP |
| Browser/API | Actual upstream UI served locally; JSON authentication and compatibility regressions | Full browser/mobile interaction campaign and exhaustive API/preset differential suite |
| Native devices | Mock and loopback HTTP snapshot/recovery tests, identity/realtime safeguards, capture races/timeouts, independent network failure, restart persistence, saved-playlist restart and UDP codec tests | Each mode, groups, actual ESP versions, direct/mixed routing, network loss, restart, missing End and runtime crashes; captured settings/power restoration and playlist restart on actual devices |
| MQTT/HA/mDNS | Real pinned Paho client against loopback MQTT wire fixture; discovery/command/retained rejection/show-gate checks | Production broker reconnect/TLS, HA application acceptance, multicast discovery and physical interoperability |
| Lifecycle | Staged install, health check, rollback/removal scripts and syntax checks | Fresh Pi install, upgrade failure injection, FPP restart, rollback and config-preserving removal |
| Publication | Public upstream-history Linux port branch, repository metadata, pinned inputs, notices, passing x86-64/arm64 CI and checksummed source packaging | Pi binary reproducibility and catalog review |

Run `bash scripts/verify.sh` and retain stdout, compiler/Python versions and commit IDs. `scripts/benchmark.py` emits JSON for a 1,000 RGB strip and 32×32 workload with 40 fps simulated time. It measures rendering only, not real-time scheduling or FPP delivery. Desktop results are not a substitute for Pi acceptance.

For Pi4 baseline, capture CPU model/OS/FPP versions, compiler, power supply, temperatures/throttling, process CPU/RSS, output protocol and controller topology. Require at least one hour at 1,000 RGB/40 fps and a separate 2D run. Record p50/p95/p99 frame-to-output latency and missed deadlines under show takeover, not just mean render time. Publish actual measurements before selecting a supported throughput limit.

For each routing topology, exercise idle ambient → Show Start → black/color sequence → song gap → pause/resume → overlap second source → end first → end second → quiet → ambient. Check physical outputs and packet captures. Include runtime kill, FPP restart, observer starvation, corrupt config, unplugged native device and stale/missing End. A failure must not block stock FPP show output. Record the interrupted ambient playlist entry and pre-show enable/selection state before and after.

Release artifacts must include exact plugin commit, pinned upstream source, compiler/dependency versions, licenses/notices, build instructions and SHA-256 checksums. Source scripts currently pin versions; toolchain/container and wheel hashes still need freezing for byte-for-byte reproducible binary releases. Keep prerelease/alpha labels until real hardware passes.
