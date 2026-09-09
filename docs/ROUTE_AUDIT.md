# Web route audit — September 8, 2026

This audit covers the Linux plugin's advertised web routes. It does not claim full ESP WLED compatibility or physical-device acceptance.

## Repairs

- Runtime login now saves an HttpOnly, SameSite=Strict cookie for one year, renewed by access checks. Existing valid session cookies are upgraded automatically. Clearing browser data, changing the token, or choosing Forget access requires another login; different browsers and hostnames have separate cookies.
- FPP's plugin page and WLED Settings query the same server-confirmed access status. Settings hides the token entry after login. Tokens are not stored in JavaScript local storage.
- Forget access clears both the plugin-scoped cookie and the legacy root cookie.
- Preset backup downloads use the plugin path. Empty palette slots no longer offer a broken download.
- Peek opens the working ambient preview. The status banner no longer blocks bottom navigation. ESP upgrade reporting is disabled.

## Verification coverage

| Surface | Evidence |
| --- | --- |
| Main UI, Settings, login alias, JS/CSS assets | Actual HTTP route inventory tests |
| JSON state/info/effects/palettes/nodes, preset export, status/config/devices/discovery/schedules/preview | Actual HTTP route inventory tests |
| Login, access status, logout | Cookie expiry, browser-cookie reload, runtime restart, stale cookie with valid bearer, legacy cookie removal regression tests |
| JSON mutation aliases, preset save/import, custom palette save/export/delete, configuration save, ownership commands | Isolated real-controller HTTP tests; no installed lighting changes |
| Schedules | Route preview plus existing scheduling/editor tests |
| Native-device commands | Missing-target HTTP rejection plus existing device simulator tests; physical devices remain unverified |
| WebSocket | Browser connection and existing protocol/authorization tests |
| Browser navigation | Effects, Segments, Presets, Colors, Info, Peek and return to Settings clicked in Chromium |
| Browser access | Login, complete browser close/reopen with persistent profile, Settings saved status, logout |
| Lighting forms | Apply lighting and nightlight start/stop exercised only in the isolated runtime |

Automated suite at this audit: 120 passing tests. Route tests are in `tests/test_runtime.py`; persistence tests are in `tests/test_auth.py`. Browser checks use `tests/ui_fixture.py` and a synthetic token.

## Remaining boundaries

- Configuration is still a JSON editor. Changes requiring runtime restart do not have a restart button here; follow the installation/service instructions. Schedules and lighting changes apply immediately.
- Discovery and sync now have live settings controls and automatic peers; the Sync shortcut opens them. See [discovery and sync](DISCOVERY_SYNC.md). Manual effect-mode enrollment and output mapping still use JSON/FPP.
- ESP flashing, Wi-Fi provisioning, GPIO, audio input, usermods, Hue, PixelForge and arbitrary filesystem editing remain unsupported. Their upstream controls are disabled where exposed; unsupported APIs may return 404/422 intentionally.
- Native-device handoff, physical output, show timing under load, and Pi performance acceptance require the hardware checklist in the project documentation. HTTP success does not establish those guarantees.


## September 9 navigation and access follow-up

The installer creates the token in `plugindata/FPP_WLED_10.x/auth.json`. The FPP-only POST helper reads it; the runtime login endpoint saves an HttpOnly cookie. WLED and Settings now offer a single **Enable lighting controls** action with its purpose stated inline. The raw token stays out of markup/local storage. Advanced manual token use remains available; direct runtime addresses cannot use the FPP helper and show that distinction.

| Entry point | Destination / result |
|---|---|
| Main WLED access prompt | Retrieve token from FPP, log in, reload so WebSocket uses saved access |
| Settings access | Same operation without leaving Settings; logout restores read-only state |
| Config / bottom Settings & access | FPP-wrapped Settings on FPP; standalone Settings on a direct runtime address |
| Timer / Peek | Settings ambient-lighting section and pixel preview |
| Sync / Nodes setup link | Discovery and synchronization settings |
| Custom palettes | Custom palette editor; empty slots have no download link |
| Former File editor | Preset import and backup section |
| Former Update WLED | Plugin updates/help on FPP; compatibility on direct access |
| Credits | Offline credits with return link to plugin |
| Settings section links | Access, lighting, timers, outputs, sync, palettes, import, compatibility anchors |
| Unauthorized settings mutation | Explicit enable-controls message and scroll to access section |
| PixelForge / reboot | Still disabled; no unsupported action is sent |

Verification: 128 automated tests pass, including the actual HTTP GET/POST route inventory and authorization/ownership tests. Chromium fixture checks cover one-click access on both pages, logout/reconnect, reload persistence, Config/Timer/Peek/Sync navigation and all Settings section anchors. The preset-import shortcut, plugin-help shortcut, credits return path and direct-runtime fallback were also followed in Chromium. Mobile Settings inspected at 320 px. The PHP fixture does not forward WebSocket upgrades; its handshake errors are a fixture limitation, not evidence of a working Apache WebSocket route. Protocol tests cover WebSocket separately. These are local checks, not a new installed-device or physical-output acceptance claim.

Recommended next workflow changes: replace output mappings and device enrollment JSON with validated forms; add a supervised runtime restart action with a clear saved-versus-active configuration indicator; show command/save feedback beside each initiating form (some success and non-authorization errors still use the shared result area). Keep unsupported ESP-only capabilities explicitly labeled instead of adding routes that imply support.


## Guided setup and runtime restart (September 9)

Outputs & devices now provides forms for RGB/RGBW pixel geometry, frame rate, FPP channel ranges and native-device ID/address/mode/groups. The existing JSON editor remains under Advanced. Guided saves retain unrelated live network/timer fields. `/api/config/status` returns the saved configuration separately from the active runtime and reports pending changes. The authenticated `/api/runtime/restart` endpoint validates saved data, refuses unsupervised execution and active/uncertain show ownership, then shuts down cleanly with status 75 for the existing systemd restart policy. FPP itself is not restarted. The page waits for a new runtime start identifier before reporting success.

Browser verification covered invalid matrix rejection, saved device enrollment, persistence after reload, pending state, 320 px layout without horizontal overflow and 1 px light-mode button borders. A separate process check verified exit status 75, relaunch with the saved frame rate and preserved ambient intent. Local suite: 130 tests. Actual network discovery and read-only JSON info requests reached three native WLED 16.0.1 devices; no lighting commands were sent. An mDNS loopback entry found on the player led to a regression test and exclusion of loopback, multicast and unspecified peer addresses.

Remaining: physical sync and takeover/recovery acceptance under shows/load, Pi benchmarks, destructive lifecycle acceptance on a spare image, and inherited artwork provenance review. Discovery enrollment is currently manual using the form; a prefilled Enroll action on discovered results would further shorten setup. Advanced pixel remapping and MQTT credentials remain advanced workflows.
