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
