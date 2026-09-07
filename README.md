# WLED for FPP 10.x — Linux alpha

An experimental FPP plugin that renders upstream WLED effects in a separate Linux process and contributes ambient channels through FPP's pre-overlay plugin hook. FPP continues to own its physical outputs and network pixel protocols.

**This is an implementation alpha, not a hardware-validated release.** Linux rendering, IPC, arbitration, API behavior and browser controls have automated/local checks. Installation and playback on stock FPP 10, Raspberry Pi 4/5, and physical WLED devices still require the acceptance campaign in [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md). Do not infer Pi performance or show handoff guarantees from desktop tests.

- Target: Raspberry Pi 4/5, aarch64, stock FPP 10, plugin ABI 6.
- Engine: WLED v16.0.1, commit `29b389df1c1aaec6ff53aea742d17063b985906c`.
- Dedicated WLED UI/API: port **8787**, configurable; FPP's existing WLED endpoints remain separate.
- 129 supported effect IDs on a strip; 171 on a matrix, retaining upstream numbering across all 220 slots. Audio, reserved and dimension-incompatible effects are marked unavailable.
- RGB/RGBW, segments, built-in and custom palettes with previews/import/editing, mapping, normal transitions, selective/partial presets, sequential or shuffled playlists, local timers, HTTP/JSON, WebSocket, optional UDP, MQTT/HA discovery and native-device enrollment.
- Explicit source-scoped show locks persist across restarts. Unknown ownership or a stale 500 ms heartbeat disables ambient. All sources must clear, followed by at least two quiet seconds, before ambient resumes.
- Native effect-mode lighting checkpoints persist across restarts and restore after shows, with identity checks and realtime-aware retries. Native saved playlists restart from the beginning; exact native playlist position remains unavailable. See [recovery details](docs/CONTROL.md#native-device-recovery).

The compatibility layer does **not** implement every WLED API or setting. Read the [compatibility matrix](docs/COMPATIBILITY.md) before importing presets or integrating a controller.

## Install and configure

See [installation, upgrades, rollback and removal](docs/INSTALL.md). Repository-based installation is provided, with [alpha source releases](https://github.com/stingerman1/FPP_WLED_10.x/releases). Pi binary releases and plugin-catalog acceptance remain pending.

```sh
cd /home/fpp/media/plugins
git clone https://github.com/stingerman1/FPP_WLED_10.x.git
cd FPP_WLED_10.x
sudo bash scripts/install.sh
```

Restart FPP through its UI after installation. Visit `http://FPP-IP:8787/settings`, log in with the locally stored token, configure channel ranges, and then enable ambient. Initial ambient output is disabled. Configuration is under `/home/fpp/media/config/plugin.FPP_WLED_10.x`, outside the plugin directory.

## Shows and native devices

The adapter observes FPP playlists, running sequences and bridge/live input. It holds ownership through playlist gaps and pauses. Explicit hooks are required for guaranteed handoff when xSchedule or another sender routes directly to devices. [Hook and API examples](docs/CONTROL.md) explain how to wait for successful Show Start, retain independent source locks and release them after the last show packet.

Native devices have exactly one enrolled mode: HTTP effects/presets, UDP synchronization, or FPP-rendered streaming. For streaming, configure DDP/E1.31/Art-Net in FPP and map channels here; this plugin does not open a second competing pixel sender. mDNS discovery only suggests candidates; enrollment is manual. Physical-device integration remains experimental.

## Develop and verify

For the current pickup point, completed work, remaining implementation, and local tooling details, read the [development handoff](docs/HANDOFF.md).

Linux requires Git, Python 3.10+, GCC/G++ with C++20 support and standard development tools. Network libraries and the local solar-calculation dependency are pinned in `requirements.txt`. Solar schedules require system timezone data (`tzdata`).

```sh
bash scripts/verify.sh
python3 scripts/benchmark.py --output build/benchmark.json
FPP_SRC=/opt/fpp/src bash scripts/build-plugin.sh
python3 scripts/verify-abi.py /opt/fpp/src build/libFPP_WLED_10.x.so
```

The last two commands require an installed FPP build. Reference-header compilation is a compile check only. [CI](https://github.com/stingerman1/FPP_WLED_10.x/actions/workflows/verify.yml) passes on Linux x86-64 and arm64; this does not replace Pi/FPP hardware acceptance.

`scripts/prepare_renderer.py` verifies the pinned Linux-port commit, unchanged upstream rendering tree and matching local platform wrappers, then applies explicit Linux substitutions. No ESP firmware is built or flashed by the plugin installer. The dedicated [Linux port branch](https://github.com/stingerman1/WLED/tree/linux-fpp-16.0.1/ports/fpp-linux) preserves upstream WLED history; its exact commit is in `upstream.lock.json`. See [architecture](docs/ARCHITECTURE.md), [third-party notices](THIRD_PARTY_NOTICES.md) and [license](LICENSE).
