# Show hooks and APIs

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
| GET `/presets.json` | Saved preset document |
| POST `/api/presets/import` | Preview and atomically merge a WLED preset catalog; authentication required, also available during shows |
| POST `/json/state` with `psave` / `pdel` | Save/edit/delete a preset, including during a show without modifying live state |
| `/ws` | WLED state/info WebSocket; login cookie or bearer header required for mutation |

Use `{"ps":1}` to recall a preset and `{"playlist":{"ps":[1,2],"dur":[100],"transition":[7],"repeat":0}}` to run a sequential playlist. Durations and transitions use upstream deciseconds. Repeat 0 is continuous. Add `"r":true` inside the playlist to shuffle each pass. Duration 0 holds an entry until `{"np":true}` advances it. `"end":255` returns to the saved preset selected before starting the playlist. Retained MQTT commands are ignored to avoid replaying stale control after reconnect.

Selective save example: `{"psave":1,"n":"Rainbow","ql":"R","ib":false,"sb":false,"sc":true}` preserves the recall-time global brightness and segment geometry. Custom JSON example: `{"psave":2,"o":true,"n":"Dim","bri":42}` stores only the brightness change. Both saves leave live output untouched during shows. Full-state saves remain the default when flags are omitted. Unsupported command strings and non-default hardware settings still reject with 422.

The quiet period begins when the last automatic or explicit owner clears. Black show frames still count as live input. A playlist pause or gap retains playlist ownership. If observation becomes stale, ambient stops and a new quiet period is required after observation recovers.

## Importing native WLED presets

Open Linux Setup, log in, and use **Import WLED presets**. Download your existing presets first, choose a native `presets.json` file or paste its contents, then preview. The report lists added/overwritten IDs, neutral settings translated, and incompatibilities. Save imports only after the whole batch passes. Reload the WLED page afterward to refresh its cached preset list.

API preview: `{"presets":{"1":{"n":"Warm","bs":0,"seg":{"cct":127,"col":["FFA000"]}}},"preview":true}`. Send the same document with `"preview":false` and the returned `revision` to save. Preview defaults to true. A changed input or saved catalog requires another preview. Invalid previews return 200 with `valid:false` and detailed errors; invalid saves return 422 and save nothing.

Imports merge by ID (1–250), preserve other presets, ignore WLED's empty `"0":{}` placeholder, and resolve playlist references across the complete batch. They preserve partial state patches and current live output, playlist position, and ownership. Neutral `bs:0`, `ledmap:0`, `cct:127`, `set:0`, `si:0`, and `bm:0` are removed with explicit translation notes. Non-default unsupported features are rejected rather than approximated. Geometry must fit the current canvas; import does not resize it. References used by existing or active playlists must remain valid.

The complete HTTP request is limited to 256 KiB; split larger files into batches, importing lighting presets before playlists that reference them. Imports do not translate legacy command strings, nested playlists, custom palettes, preset-reference commands, or ESP hardware features. Editing an imported preset during a show is allowed; recalling it still waits for ownership to clear.

## Native-device recovery

Enrolled **effect-mode** devices are polled for ambient lighting settings every two seconds while ambient is allowed. Changed checkpoints persist in `native-snapshots.json`, alongside other user settings. The first explicit Show Start from allowed ambient drains prior commands, attempts a fresh read-only capture for up to two seconds across devices, and waits for FPP revocation acknowledgment. Later overlapping starts do not replace that checkpoint. Configure remote hook clients for at least a ten-second response timeout; the bundled CLI and FPP commands use ten seconds.

After every show source clears and the quiet period ends, recovery restores captured power, brightness, segment settings, colors, geometry, and supported preset selection. It checks the device MAC/address and realtime flag before each write, sends no realtime override, and suppresses notifications for restoration requests. A still-live or unreachable device remains pending and retries independently, at most once every two seconds. New ambient commands supersede a pending restore. FPP-stream devices receive no snapshot polling or HTTP restoration; sync devices retain their UDP command behavior.

Automatic takeover uses the last ambient checkpoint; it cannot obtain a guaranteed pre-show sample after live input has already started. Capture failure or timeout retains the last checkpoint and appears in device status. If no checkpoint matches the latest desired command, resume falls back to that command when one exists. Saved checkpoints also support ambient recovery after runtime restart. An address or MAC mismatch blocks snapshot replay; use an explicit new ambient command after confirming enrollment to establish a new checkpoint.

Saved native playlists restart **from the beginning**, followed by restoring captured global power/brightness. WLED does not expose the native cursor, remaining repeats, or shuffle position in its regular state API. Preset contents stay on the device and are not backed up by this feature. Unsaved native playlists and active nightlights report unsupported recovery and do not silently fall back to an unrelated lighting state. Effect animation phase and raw pixel buffers are not captured. Existing autonomous effects/playlists still require the show to take realtime ownership; the plugin does not forcibly stop them during a show.

Inspect `/api/devices` or the setup page's device status for `snapshot_available`, `snapshot_time`, `restore_pending`, `recovery`, and `recovery_detail`. The timestamp records the persisted checkpoint, which is rewritten only when settings change. Network operations run on bounded device workers, outside FPP's output callback. These behaviors have simulator tests; physical WLED acceptance is still required.
