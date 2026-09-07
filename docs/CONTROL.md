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
