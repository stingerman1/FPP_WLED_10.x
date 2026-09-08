# Development handoff — 2026-09-07

## Pickup point

The latest increment implements nightlight mode 3 using the existing upstream Sunrise effect 104. Starting from off gives sunrise; starting from on gives sunset. Sunrise holds a completed static sun, sunset restores prior effects and turns off, and cancellation restores prior effects with power on. Shows pause both animation phase and countdown. Same-animation restart resets segment runtime using existing APIs without an intermediate output frame. Selected segments must be unfrozen and have at least two virtual pixels; duration is limited to 1-60 minutes. Public state exposes temporary effects, while ordinary preset snapshots/process restart retain the underlying saved selection. The setup UI exposes mode 3 and hides its unused target field. Main files: `runtime/nightlight.py`, `runtime/state.py`, `runtime/service.py`, `web/settings.html`, and `tests/test_sunrise.py`. Local verification passed all 111 tests, renderer/IPC checks and syntax checks. Desktop/mobile browser layout checks passed. Actual effect-frame tests cover rise/set brightness, restart, show phase pause, restoration and matrix output. Browser checks cover animation start and mode-specific controls. No renderer fork changes were required. Next: custom transition styles and remaining portable effects; native-device nightlight recovery is still unsupported.

The project is an implemented, publicly available **alpha**, not a hardware-validated release. Continue expanding software compatibility; verification is not the only remaining work. The user asked to save current status for later pickup. No implementation task is currently in progress.

The preceding implementation commit was **`0f93eae`**: solar scheduling and the Follow the daylight editor. Its 102 tests and x86-64/ARM64 CI checks passed. The renderer-port pin is unchanged; this increment adds Python/UI integration only. Check the current `main` workflow for the animation increment.

The working tree was clean before this handoff documentation was added. The latest changes are pushed to `origin/main`. The existing `v0.1.0-alpha.1` source release predates recent compatibility and recovery work; installing that release does not include everything described here. No Pi binary release has been published.

## User intent and working preferences

Build a publicly installable FPP 10 plugin for Raspberry Pi 4/5, 64-bit. Run upstream WLED lighting locally, manage native WLED devices, yield to shows, and restore ambient operation afterward. Preserve stock FPP and retain upstream WLED effect IDs and supported preset formats.

The user repeatedly asked to keep building without repeated confirmation questions. Continue ordinary implementation, tests, documentation, commits, and pushes within this established scope. Do not claim hardware acceptance or full WLED compatibility. Keep excluded hardware features explicit; accepting an unsupported setting without implementing its behavior is not compatibility.

## Repositories and pins

| Item | Value |
|---|---|
| Workspace | `C:\Github\FPP_WLED_10.x` |
| Public plugin repository | `https://github.com/stingerman1/FPP_WLED_10.x.git` |
| Working branch | `main` |
| WLED upstream release | `v16.0.1`, commit `29b389df1c1aaec6ff53aea742d17063b985906c` |
| Public Linux port | `stingerman1/WLED`, branch `linux-fpp-16.0.1` |
| Pinned Linux-port commit | `6aaf34dd2fcbdc9e3211ec395d0d1f449bfe4b4e` |
| FPP reference | `v10.0`, commit `370e62ed7e8c8318da6ee5b01312b8b75082d952`, plugin ABI 6 |
| Existing source prerelease | `v0.1.0-alpha.1`, targeting `e4abc7b` |

`upstream.lock.json` is authoritative. The Linux port preserves upstream history; the fork's unrelated pre-existing default branch was preserved. Changes to `runtime/linux` require corresponding port-branch work and updating the exact pin: preparation checks mirrored wrapper files and the original upstream rendering tree. Python integration changes do not require changing the WLED fork.

## Implemented foundation

- Actual upstream rendering code in a separate supervised Linux process: 129 supported strip effects and 171 matrix effects across 220 stable IDs. RGB/RGBW, segments, geometry/mapping, built-in/custom palettes, ordinary transitions, and representative 2D effects are implemented.
- FPP channel-data adapter contributes fresh ambient frames before overlays. FPP retains physical drivers, channel ordering, DDP/E1.31/Art-Net outputs. Network/rendering work stays outside FPP's output callback.
- Versioned local IPC, 500 ms freshness limit, automatic playlist/sequence/live ownership, persistent source-scoped explicit locks, and a two-second quiet period. Live ambient changes reject during ownership; saved preset editing remains allowed.
- Upstream main WLED UI and Linux setup page, configurable port 8787, JSON/HTTP APIs, WebSocket state updates, bearer/cookie authentication, and a protected local control socket.
- Optional UDP notifier v12, MQTT/Home Assistant discovery and commands, mDNS suggestions, manual native-device enrollment, individual/group commands, and effect/sync/FPP-stream mode exclusivity.
- Local weekday timers; presets and sequential/shuffled playlists persist. Local ambient playlists restart the interrupted entry after shows.
- Installer with installed-FPP ABI checks, staged immutable releases, supervised service, health check, upgrade/rollback/removal scripts, and configuration outside the plugin checkout. Installation does not automatically restart FPP.

## Recent compatibility work

### `3094d93` — preset and playlist semantics

Implemented selective saves (`ib`, `sb`, `sc`), partial JSON presets (`o:true`), quick-load labels, stock preset padding, neutral hardware-default translation, scalar/short duration arrays, duration-zero hold, explicit advance (`np`), shuffled playback, and return-to-prior-preset (`end:255`). See `runtime/state.py` and `tests/test_compatibility.py`.

### `25356ad` — native WLED preset-file import

`POST /api/presets/import` and Linux Setup support upload/paste, translation preview, per-entry errors, complete-batch playlist reference validation, and atomic merge. Existing IDs are overwritten only on save; other presets remain. Revision checking binds the preview to both input and the existing catalog. Live state, playlist position, and show locks remain unchanged. HTTP request limit is 256 KiB.

Key files: `runtime/preset_import.py`, `web/settings.html`, `tests/test_preset_import.py`, and the real-daemon import checks in `tests/test_process.py`.

### `ccfebd9` — native effect-mode recovery

- Poll effect-mode devices every two seconds while ambient is allowed. Persist changed lighting checkpoints in `native-snapshots.json`.
- The first explicit Show Start from allowed ambient drains previous commands, attempts a fresh read-only capture for up to two seconds, and waits for FPP revocation acknowledgment. Overlapping starts do not replace the original checkpoint. Late capture responses are discarded.
- Restore lighting settings after ownership and quiet-period gates clear. Check address/MAC and require an explicitly false native realtime flag before each write. Never send `lor` or force realtime exit. Suppress notifications for restore requests.
- Retry pending restoration independently when a device remains live or unreachable. New ambient commands supersede pending recovery. Snapshots record associated desired commands to avoid restoring an older intent after a crash.
- Native saved playlists restart from the beginning, followed by restoring global power/brightness. Static lighting restores segment settings, colors, geometry, and supported preset-direct metadata.
- CLI and asynchronous FPP command socket timeouts are now ten seconds to accommodate the bounded capture/drain/acknowledgment work.

Key files: `runtime/native_restore.py`, `runtime/devices.py`, `runtime/service.py`, `plugin/commands.hpp`, `scripts/wledctl.py`, `tests/test_native_restore.py`, and controller integration coverage in `tests/test_runtime.py`.

Recovery limitations remain material:

- Native WLED's regular state API does not expose playlist cursor, remaining repetitions, or shuffle position. Do not claim exact native interrupted-entry recovery. Local runtime playlists do support interrupted-entry restart.
- Unsaved native playlists and active nightlights are explicitly unsupported for checkpoint recovery. Effect phase and raw pixel buffers are not captured. Native preset definitions remain on the device and are not backed up.
- Automatic takeover uses the last ambient checkpoint. Explicit capture is best effort; failure retains an older checkpoint and reports the failure. Without a checkpoint matching current desired intent, effect mode retains last-command fallback. Sync mode retains its existing command fallback; FPP-stream devices receive no recovery HTTP traffic.
- Already-running native effects/playlists are not forcibly stopped by Show Start. Direct or mixed routing still requires explicit hooks and a show stream that takes realtime ownership.

## Next implementation priorities

The last priority discussed was native recovery, then custom palettes and preset-command compatibility. Native recovery and custom palettes now have implementations; their documented limits remain.

The first lighting-only command subset is implemented. Next, extend legacy HTTP response compatibility and preset-reference resolution against pinned WLED sources. Preserve show ownership and atomic validation; detect cycles and validate complete import catalogs before accepting reference chains.

Other outstanding software work:

1. Legacy `/win` HTTP endpoint, broader command keys, preset-reference chains and random expressions, boot presets, and nested local playlists. Lighting-only JSON `win` strings and deterministic numeric cycling now work.
2. Custom transition styles and native-device nightlight recovery. Local nightlight modes 0-3 and sunrise/sunset scheduling are now implemented.
3. Review remaining unsupported effects individually; distinguish portable missing implementations from audio-dependent or dimension-incompatible IDs.
4. Broader configuration UI/API coverage and fragmented WebSocket requests. Lighting controls, nightlights, pixel preview and palette JSON editing/previews are implemented; arbitrary filesystem editing remains excluded.
5. Resolve FPP models by name; currently users supply resolved channel ranges. Native custom HTTP ports and credentials are not implemented.
6. Publish a newer alpha source release, produce reproducible Pi binary assets, and submit plugin-catalog metadata once validated. Catalog acceptance is upstream's decision.

First-release exclusions: ESP firmware flashing, Wi-Fi provisioning, ESP-NOW, GPIO peripherals, audio-reactive input, arbitrary usermods, and Philips Hue. These require explicit additional backends or scope expansion, not field aliases.

## Verification environment and commands

Development host is Windows/PowerShell with WSL distribution `Ubuntu-24.04`. Run Linux commands from the repository directory. Existing ignored build outputs include `build/libwled_linux.so` and `build/libFPP_WLED_10.x.so`. Optional Python dependency wheels are unpacked in `build/python-deps`.

Full Python suite from PowerShell:

```powershell
wsl -d Ubuntu-24.04 --exec env PYTHONPATH=build/python-deps python3 -m unittest discover -s tests -p test_*.py -v
```

Full build/check script from PowerShell:

```powershell
wsl -d Ubuntu-24.04 --exec env PYTHONPATH=build/python-deps bash scripts/verify.sh
```

Local reference-header adapter compilation:

```powershell
wsl -d Ubuntu-24.04 --exec g++ -std=c++20 -O2 -fPIC -shared -pthread -I.upstream/fpp/src -I.upstream/jsoncpp/include plugin/plugin.cpp -o build/libFPP_WLED_10.x.so
```

The local WSL system lacks installed jsoncpp headers; the existing `.upstream/jsoncpp/include` tree supplies them for this compile check. Omitting that include path produces incomplete `Json::Value` errors. CI installs `libjsoncpp-dev` instead. A reference-header compile does not prove ABI loading on an installed FPP system.

CI workflow: `.github/workflows/verify.yml`, Ubuntu x86-64 and ARM64. It builds the renderer, runs sanitizer/Python/syntax checks, compiles against pinned FPP headers, and uploads renderer benchmarks. There is a non-blocking Node 20 action-deprecation annotation; the latest run passed.

Earlier port-level regression checks also passed upstream `npm test` (16 tests), the standalone `ports/fpp-linux` build, and `pio run -e esp32dev`. Those checks predate the Python compatibility increments; no ESP firmware was flashed.

Browser fixture, when needed:

```powershell
wsl -d Ubuntu-24.04 --exec env PYTHONPATH=build/python-deps python3 tests/ui_fixture.py
```

It serves a temporary runtime at `http://localhost:18787` with a simulated FPP observer. Read the test-only token from the fixture source. The Playwright skill/CLI was used for prior UI checks; browser artifacts are ignored under `output/playwright` and `.playwright-cli`. Stop the fixture after use. No fixture or browser session is intentionally left running at this handoff.

## GitHub and release tooling notes

Normal `gh` authentication on this host was invalid, but Git Credential Manager worked for Git operations. Ignored `build/github-cli.py` retrieves credentials through captured `git credential fill` output and passes the token only in a child process environment. Never print credentials or put them in tracked files.

Example CI lookup from PowerShell:

```powershell
$pickupCommit = git rev-parse HEAD
python build/github-cli.py run list --repo stingerman1/FPP_WLED_10.x --commit $pickupCommit --limit 1 --json databaseId,status,conclusion,url
```

Use the full commit SHA; abbreviated commit filters previously returned no results. The helper and local dependency caches are ignored and may not exist on a fresh machine; recreate equivalent tooling or use that machine's authenticated GitHub client if needed.

`build/publish-alpha.py` is an ignored helper hardcoded for `v0.1.0-alpha.1`. Do not rerun it unchanged to publish a new release or overwrite existing assets. Prepare a new version, notes, manifest, and checksummed assets deliberately. Existing `v0.1.0-alpha.1` assets are source packages, not Pi binaries.

## Hardware acceptance still open

No actual Pi 4/5, installed FPP daemon, or native WLED hardware was available for acceptance in this session. The HTTP and FPP observer tests use simulators. Still required: real installation/ABI loading, frame delivery, scheduled/standalone/remote/live playback, gaps/pauses/black frames, mixed routing, native checkpoint restoration, crash/restart/network-loss behavior, lifecycle tests, and Pi performance/thermal benchmarks.

Read [ACCEPTANCE.md](ACCEPTANCE.md), [COMPATIBILITY.md](COMPATIBILITY.md), [CONTROL.md](CONTROL.md), [INSTALL.md](INSTALL.md), and [VALIDATION.md](VALIDATION.md) before making release-support claims. Desktop renderer speed is not a supported Pi output limit.
