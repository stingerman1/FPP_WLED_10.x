# Show hooks and APIs

## Clock, sunrise and sunset schedules

Open **Linux Setup ? Follow the daylight**. Enable location, enter latitude/longitude and an IANA timezone (for example `America/Chicago`), then add timers using existing preset IDs. Select weekdays and an offset from -720 to +720 minutes for solar events. Preview upcoming events, then save. This dedicated editor applies schedules immediately; editing the raw Configuration JSON still requires a runtime restart. No location lookup or solar API is contacted.

`GET /api/schedules` returns active definitions, the configuration revision, today's solar times and upcoming occurrences. Authenticated `POST /api/schedules` accepts the following preview request; set `preview:false` and include the returned `revision` to save:

```json
{
  "location": {"latitude": 41.88, "longitude": -87.63, "timezone": "America/Chicago"},
  "timers": [
    {"event": "sunset", "offset": -30, "days": [0,1,2,3,4,5,6], "preset": 1, "enabled": true},
    {"hour": 23, "minute": 0, "days": [0,1,2,3,4,5,6], "preset": 2}
  ],
  "preview": true
}
```

At most 64 timers are supported. Clock timers retain the original hour/minute format; `event:"clock"` is optional. Without a location, clock timers use the Pi's local time. A configured timezone applies to all timers and follows its DST rules. Named-zone clock times skipped by spring-forward do not fire; repeated fall-back times use their first occurrence. Solar offsets count elapsed minutes across DST, and weekday filtering uses the solar event's date even when an offset crosses midnight. Solar timestamps are rounded down to the containing minute for dispatch.

The local renderer recalls presets only while ambient owns the outputs. Events during shows, quiet periods, disabled ambient, or unavailable ownership are consumed and skipped. Missed minutes are not caught up. `timers-fired.json` records events before dispatch, preventing duplicates across ordinary restarts and clock corrections; records older than eight days are pruned when a new event is recorded. Identical timer definitions are deduplicated. Changing a definition/location can create a new event in the current minute. A ledger write failure prevents dispatch. Preset-editing behavior remains unchanged: deleting a referenced preset makes its future timer log a skipped recall.

Previewing/saving schedules leaves current lighting and show locks unchanged. Saves reject stale configuration revisions and preserve unrelated pending configuration changes. Preset IDs must exist when saving. Preview dates extend through the next eight calendar days; no occurrence means disabled, filtered weekdays, or no solar event in that window. Polar day/night never substitutes an arbitrary time.

Solar calculations use pinned [Astral 3.2](https://sffjunkie.github.io/astral/package.html), with its standard horizon/refraction calculation and observer elevation zero. Terrain, weather, and custom horizon corrections are not modeled. The Pi needs an accurate clock and system timezone data (`tzdata`). Scheduling sunrise is separate from the still-unimplemented WLED nightlight sunrise animation mode.

## Lighting panel and nightlights

Open **Linux Setup → Ambient lighting** (or WLED's nightlight button) for a live pixel preview, supported effect selection, primary/secondary RGB colors, RGBW white channels, brightness, ordinary transition duration, and nightlight controls. Authenticate through Runtime access first. Live changes require ambient ownership.

`POST /json/state` accepts `{"nl":{"on":true,"dur":30,"mode":1,"tbri":0}}`. Modes are 0 (wait, then set brightness), 1 (linear brightness fade), and 2 (brightness plus primary-to-secondary color fade for each selected segment). Duration is 1–255 whole minutes; target brightness is 0–255. Zero target turns off while remembering the starting brightness. `{"nl":{"on":false}}` stops at the current light level. `GET /json/state` exposes `nl.rem` in seconds, or -1 when inactive. Rendering bypasses ordinary transitions while the nightlight is active.

Nightlight time advances only while ambient is allowed. Shows, uncertain ownership, disabled ambient, and the quiet period all pause the countdown; it resumes once ambient is allowed. A new lighting/preset selection cancels the timer. Changing nightlight settings restarts an active timer from the current level. Saving/editing presets does not change the active timer. Explicit nightlight presets can be saved/imported and recalled; active nightlights are not allowed as playlist entries. Process restarts restore the last saved lighting state with the nightlight stopped, rather than replaying a timed action. Completion is saved; intermediate fade frames are not written to disk.

These modes run in the local renderer and flow through FPP mappings. Native-device nightlight control/recovery, sunrise mode 3, and custom transition styles remain unsupported. Solar scheduling is described below.

`GET /api/preview` returns the latest rendered RGB/RGBW output as `[pixelIndex, R, G, B, optional W]` entries, geometry, and sample stride. At most 4,096 samples are returned. It returns no pixels while ambient is suspended. The setup page polls twice per second only while visible and preview is enabled, wraps strips into rows, and displays matrix geometry. White is approximated by adding it to RGB for the screen. This is the runtime frame after its pixel mapping, before FPP channel mappings/overlays; it does not verify physical outputs or display show data.

FPP commands registered by the adapter are **WLED Show Start**, **WLED Show End**, **WLED Ambient Enable**, **WLED Ambient Disable**, and **WLED Status**. Show Start/End take a source identifier. Use stable, distinct identifiers for independently overlapping show producers. The `fpp:` namespace is reserved for automatic observers.

From the Pi, as the fpp user:

```sh
python3 /home/fpp/media/plugins/FPP_WLED_10.x/scripts/wledctl.py show-start xschedule:main
# Begin playback only after exit status 0.
python3 /home/fpp/media/plugins/FPP_WLED_10.x/scripts/wledctl.py show-end xschedule:main
```

For xSchedule mixed routing, run Show Start before the first output packet and wait for success. Run Show End only after the final show packet, outside individual song boundaries. Retain the lock across gaps and pauses. A failed start can have stored the lock even if acknowledgment timed out: do not begin direct playback until takeover succeeds. A missing End intentionally leaves ambient suspended, including after restart. Clear a stale source with a matching End only when that source has stopped.

The plugin cannot guarantee execution order inside arbitrary xSchedule scripts. Configure your scheduler to treat a failed hook as a playback failure. If it cannot wait for a successful HTTP/command response, manually acquire the persistent lock before starting the schedule. No automatic expiry is used for explicit locks.

Remote hook request (authenticate using your locally stored token):

```http
POST /api/command HTTP/1.1
Host: FPP-IP:8787
Authorization: Bearer TOKEN
Content-Type: application/json

{"operation":"show-start","source":"xschedule:main"}
```

Other operations are `show-end`, `ambient-enable`, `ambient-disable`, `status`. Ambient changes during show ownership, the quiet period or disabled ambient return **409**; unsupported fields return **422**; missing authentication returns **401**. Read-only APIs are public on the configured bind address. Authentication is separate from FPP's login.

| Route | Purpose |
|---|---|
| GET `/api/status` | Enabled/allowed state, locks, observer freshness, unsupported capabilities, device results |
| POST `/api/command` | Ownership and ambient controls |
| GET/POST `/api/config` | Read or validate/save configuration; restart service after saving |
| GET `/api/devices`, `/api/discovery` | Enrolled device status and mDNS suggestions |
| POST `/api/devices/command` | `{"target":"porch","state":{"ps":1}}` or `{"target":"group:outside","state":{"seg":{"fx":9}}}` |
| GET `/json`, `/json/si`, `/json/state`, `/json/info` | WLED-compatible supported state/info |
| POST `/json/state` | e.g. `{"bri":128,"seg":{"fx":9,"fxdef":true}}` |
| GET `/json/effects`, `/json/fxdata`, `/json/palettes` | Stable IDs and metadata |
| GET `/json/palx?page=N` | Eight palette previews per page; `m` is the last page and `p` maps stable palette IDs to stops or dynamic color tokens |
| GET/POST `/api/palettes` | List custom palette source/IDs/previews, or save/delete one slot |
| GET `/paletteN.json` | Export saved custom slot N as a native WLED palette document |
| GET `/presets.json` | Saved preset document |
| POST `/api/presets/import` | Preview and atomically merge a WLED preset catalog; authentication required, also available during shows |
| POST `/json/state` with `psave` / `pdel` | Save/edit/delete a preset, including during a show without modifying live state |
| `/ws` | WLED state/info WebSocket; login cookie or bearer header required for mutation |

Use `{"ps":1}` to recall a preset and `{"playlist":{"ps":[1,2],"dur":[100],"transition":[7],"repeat":0}}` to run a sequential playlist. Durations and transitions use upstream deciseconds. Repeat 0 is continuous. Add `"r":true` inside the playlist to shuffle each pass. Duration 0 holds an entry until `{"np":true}` advances it. `"end":255` returns to the saved preset selected before starting the playlist. Retained MQTT commands are ignored to avoid replaying stale control after reconnect.

Selective save example: `{"psave":1,"n":"Rainbow","ql":"R","ib":false,"sb":false,"sc":true}` preserves the recall-time global brightness and segment geometry. Custom JSON example: `{"psave":2,"o":true,"n":"Dim","bri":42}` stores only the brightness change. Both saves leave live output untouched during shows. Full-state saves remain the default when flags are omitted. Unsupported commands and non-default hardware settings still reject with 422.

Lighting command presets can be saved with `{"psave":3,"o":true,"n":"Brighter","win":"A=~10&SX=128"}`. The command stays relative and is evaluated each time it is recalled, including playlist entry restarts. Without `o:true`, saving produces a resolved state snapshot. Imported `win` presets retain their command strings. Supported keys are `A` (global brightness), `T` (0 off, 1 on, 2 toggle), `SS` (existing segment), `FX`, `SX`, `IX`, `RV`, `MI`, and primary/secondary `R/G/B/W` and `R2/G2/B2/W2`. Colors and effect controls apply to selected segments, or only `SS` when supplied; reverse/mirror apply to the addressed segment. Unknown or duplicate keys reject the complete request. Use authenticated `POST /json/state` with `{"win":"A=42&SX=128"}`; the legacy GET `/win` endpoint is not implemented. Alongside `win`, only `n`, `ql`, `v`, and `transition` are accepted.

JSON brightness and segment `fx/sx/ix/bri/c1/c2/c3` accept decimal strings, `~`/`~-` (one-step wrap), `~10`/`~-10` (clamped steps), and `w~10`/`w~-10` (wrap when already at an endpoint). Bounded expressions such as `{"ps":"1~4~"}` cycle preset IDs; missing presets reject without changing playback. Random expressions, palette expressions, preset-reference chains, and side-effect commands such as legacy `PS`/`PL` remain unsupported. Unsupported effect IDs still reject instead of being silently skipped.

The quiet period begins when the last automatic or explicit owner clears. Black show frames still count as live input. A playlist pause or gap retains playlist ownership. If observation becomes stale, ambient stops and a new quiet period is required after observation recovers.

## Importing native WLED presets

Open Linux Setup, log in, and use **Import WLED presets**. Download your existing presets first, choose a native `presets.json` file or paste its contents, then preview. The report lists added/overwritten IDs, neutral settings translated, and incompatibilities. Save imports only after the whole batch passes. Reload the WLED page afterward to refresh its cached preset list.

API preview: `{"presets":{"1":{"n":"Warm","bs":0,"seg":{"cct":127,"col":["FFA000"]}}},"preview":true}`. Send the same document with `"preview":false` and the returned `revision` to save. Preview defaults to true. A changed input or saved catalog requires another preview. Invalid previews return 200 with `valid:false` and detailed errors; invalid saves return 422 and save nothing.

Imports merge by ID (1–250), preserve other presets, ignore WLED's empty `"0":{}` placeholder, and resolve playlist references across the complete batch. They preserve partial state patches and current live output, playlist position, and ownership. Neutral `bs:0`, `ledmap:0`, `cct:127`, `set:0`, `si:0`, and `bm:0` are removed with explicit translation notes. Non-default unsupported features are rejected rather than approximated. Geometry must fit the current canvas; import does not resize it. References used by existing or active playlists must remain valid.

The complete HTTP request is limited to 256 KiB; split larger files into batches, importing lighting presets before playlists that reference them. Imports accept the lighting-only `win` subset above, but do not translate nested playlists, preset-reference commands, or ESP hardware features. Import custom palette files separately before presets that reference their IDs. Editing an imported preset during a show is allowed; recalling it still waits for ownership to clear.

## Native-device recovery

Enrolled **effect-mode** devices are polled for ambient lighting settings every two seconds while ambient is allowed. Changed checkpoints persist in `native-snapshots.json`, alongside other user settings. The first explicit Show Start from allowed ambient drains prior commands, attempts a fresh read-only capture for up to two seconds across devices, and waits for FPP revocation acknowledgment. Later overlapping starts do not replace that checkpoint. Configure remote hook clients for at least a ten-second response timeout; the bundled CLI and FPP commands use ten seconds.

After every show source clears and the quiet period ends, recovery restores captured power, brightness, segment settings, colors, geometry, and supported preset selection. It checks the device MAC/address and realtime flag before each write, sends no realtime override, and suppresses notifications for restoration requests. A still-live or unreachable device remains pending and retries independently, at most once every two seconds. New ambient commands supersede a pending restore. FPP-stream devices receive no snapshot polling or HTTP restoration; sync devices retain their UDP command behavior.

Automatic takeover uses the last ambient checkpoint; it cannot obtain a guaranteed pre-show sample after live input has already started. Capture failure or timeout retains the last checkpoint and appears in device status. If no checkpoint matches the latest desired command, resume falls back to that command when one exists. Saved checkpoints also support ambient recovery after runtime restart. An address or MAC mismatch blocks snapshot replay; use an explicit new ambient command after confirming enrollment to establish a new checkpoint.

Saved native playlists restart **from the beginning**, followed by restoring captured global power/brightness. WLED does not expose the native cursor, remaining repeats, or shuffle position in its regular state API. Preset contents stay on the device and are not backed up by this feature. Unsaved native playlists and active nightlights report unsupported recovery and do not silently fall back to an unrelated lighting state. Effect animation phase and raw pixel buffers are not captured. Existing autonomous effects/playlists still require the show to take realtime ownership; the plugin does not forcibly stop them during a show.

Inspect `/api/devices` or the setup page's device status for `snapshot_available`, `snapshot_time`, `restore_pending`, `recovery`, and `recovery_detail`. The timestamp records the persisted checkpoint, which is rewritten only when settings change. Network operations run on bounded device workers, outside FPP's output callback. These behaviors have simulator tests; physical WLED acceptance is still required.

## Custom palettes

Open **Linux Setup → Custom palettes**. Choose a slot, import a native `paletteN.json` or paste/edit its contents, and save. The preview shows the compiled gradient. Reload the WLED page to refresh its palette list. Selecting a palette-using effect makes the custom palette entries visible in the upstream UI. Slot 0 maps to palette ID 200; slot 128 maps to ID 72. Import required palettes before presets that reference those IDs.

Authenticated save example: `POST /api/palettes` with `{"slot":0,"palette":[0,"FF0000",128,"00FF00",255,"0000FF"]}`. Numeric stops work too: `{"slot":0,"palette":[0,255,0,0,255,0,0,255]}`. Export uses `GET /palette0.json`. Delete with `{"slot":0,"delete":true}`, or the upstream-compatible standalone `POST /json/state` body `{"rmcpal":0}`. Slot numbers and palette IDs are different: `rmcpal` takes a slot; segment `pal` takes an ID.

Deletion rejects palettes referenced by current state or any saved preset. Creating or editing inactive saved palettes is allowed during shows; changing the currently selected palette while ambient is suspended returns 409. Invalid gradients return 422. Preview requests do not advance the renderer or change lighting state. Definitions persist atomically in `custom-palettes.json`; a storage failure leaves the loaded table unchanged. A content revision invalidates upstream browser preview caches even when slot counts stay the same.

This is a JSON/gradient editor, not native WLED's arbitrary filesystem editor. It accepts 2–18 stops from 0 through 255, with RGB colors. It does not transmit palette definitions to enrolled native devices. Before rolling back to code without custom-palette support, select built-in palettes or restore a compatible settings backup; older runtimes cannot load state that selects a custom palette.
