# FPP catalog readiness — 2026-09-11

The plugin is not catalog-approved. Local checks and CI do not replace the
upstream submission check or testing installed release/nightly images.

## Completed software work

- Native `shutdown()` requests worker stop, withdraws commands, and returns a
  readiness predicate. It no longer joins the worker on FPP's shutdown caller.
  Destruction joins after readiness; a defensive join also protects direct
  destruction. The worker test deliberately holds a worker while requesting
  shutdown to prove the request does not wait for completion.
- Socket-address copies use bounded writes. Legacy iframe attributes are escaped.
- Release/nightly header compilation runs on x64 and ARM CI, including a weekly
  check for upstream changes. Artifacts record exact FPP commits. This is source
  compatibility evidence, not installation or playback qualification.
- Acceptance records now distinguish successful FPP04 upgrades and browser
  checks from the outstanding physical-output and fresh-image campaigns.

## Actual upstream checker result

Local verification passed: 162 Python tests, native frame and worker checks under
AddressSanitizer/UndefinedBehaviorSanitizer, and adapter compilation against:

- FPP 10.0: `370e62ed7e8c8318da6ee5b01312b8b75082d952`.
- Current master/nightly source: `fe372d4e1ae2e3eef6217b44164b1f105d61fcd2`.

Checker: `FalconChristmas/fpp-data` commit
`74baf92cad2be58bdfa395b4a6af5d7a4a10aacf`, using its unmodified linter and schema.

After the copy/escaping fixes, the local check reports:

| Severity | Finding | Disposition |
| --- | --- | --- |
| Blocker | `server-bind-all-interfaces` | Requires upstream review; explanation below. |
| Optional | `restart-likely-not-required` | Retain restart flag until real FPP hot-reload/command-result lifetime testing proves it unnecessary. |

There are no remaining best-practice findings in this check. The blocker is not
suppressed or relabeled as passed. No submission issue or maintainer comment has
been sent by this repair pass.

The flagged socket is `runtime/discovery.py`'s **UDP port 65506**, created with
`SOCK_DGRAM` and used for WLED node announcements. It must receive broadcasts
from other controllers on LAN interfaces. It is not an HTTP listener and cannot
serve the runtime HTTP/API routes. Apache proxies the separate Unix `web.sock`;
the optional direct HTTP listener defaults to loopback and requires authorization
for writes. The linter's rule matches any wildcard Python bind anywhere in a
repository containing `ProxyPass`, without checking the transport or endpoint.
Changing discovery to loopback would break the feature, not fix an HTTP exposure.
Maintainer review or a transport-aware upstream rule is needed here.

Reproduce against committed source (Python 3.12+, Git and `jsonschema` required):

```sh
git clone https://github.com/FalconChristmas/fpp-data.git .upstream/fpp-data
git -C .upstream/fpp-data checkout 74baf92cad2be58bdfa395b4a6af5d7a4a10aacf
python3 scripts/check-submission.py .upstream/fpp-data
```

The helper scans a clean archive of HEAD, records plugin/checker commits and every
finding in `build/submission-report.json`, and exits nonzero on any blocker or
best-practice finding. It never posts to GitHub.

## Still required

1. Installed-image testing on the latest released FPP and current nightly,
   including fresh installation, playback, repeated takeover/resume and removal.
2. Pi4/Pi5 performance/thermal soak, physical RGB/RGBW/2D outputs, real native WLED
   discovery/sync, MQTT/HA and mixed-routing failure recovery. See ACCEPTANCE.md.
3. Submission contact/category information and actual upstream checker/maintainer
   review. A passing local schema is not a listing decision.
4. Keep library unloading disabled until all FPP-owned asynchronous command
   results can be proven gone. Counting completed requests alone cannot prove
   their result objects or virtual methods are no longer referenced.

Refactoring embedded settings JavaScript and reproducible binary packaging remain
maintainability/publication work; they are not claimed as confirmed checker
blockers. The FPP device-type code remains a private WLED extension.
