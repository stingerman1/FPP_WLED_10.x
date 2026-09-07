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
| POST `/json/state` with `psave` / `pdel` | Save/edit/delete a preset, including during a show without modifying live state |
| `/ws` | WLED state/info WebSocket; login cookie or bearer header required for mutation |

Use `{"ps":1}` to recall a preset and `{"playlist":{"ps":[1,2],"dur":[100],"transition":[7],"repeat":0}}` to run a sequential playlist. Durations and transitions use upstream deciseconds. Repeat 0 is continuous. Add `"r":true` inside the playlist to shuffle each pass. Duration 0 holds an entry until `{"np":true}` advances it. `"end":255` returns to the saved preset selected before starting the playlist. Retained MQTT commands are ignored to avoid replaying stale control after reconnect.

Selective save example: `{"psave":1,"n":"Rainbow","ql":"R","ib":false,"sb":false,"sc":true}` preserves the recall-time global brightness and segment geometry. Custom JSON example: `{"psave":2,"o":true,"n":"Dim","bri":42}` stores only the brightness change. Both saves leave live output untouched during shows. Full-state saves remain the default when flags are omitted. Unsupported command strings and non-default hardware settings still reject with 422.

The quiet period begins when the last automatic or explicit owner clears. Black show frames still count as live input. A playlist pause or gap retains playlist ownership. If observation becomes stale, ambient stops and a new quiet period is required after observation recovers.
