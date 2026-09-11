# Code and FPP integration review — 2026-09-11

**Verdict: useful alpha foundation, but not ready for a blanket best-practices or
full FPP-conformance sign-off.** The findings below remain open; this was a review,
not a repair pass. Fix the lifecycle and API findings before claiming beta readiness.

Reviewed plugin commit `2162034` and receiver fork commit `16ac3ee4` on
`stingerman1/WLED:fpp-node-type-16.0.1`. Compared with the current
[FPP integration guide](https://github.com/FalconChristmas/fpp-plugin-Template/blob/ef15069fc9322470397ab44afdf837a5e0d330a6/PLUGIN_GUIDELINES.md)
and metadata schema at `ef15069fc9322470397ab44afdf837a5e0d330a6`.
This updates the scope of TEMPLATE_AUDIT.md; its older pass descriptions are not
a current certification. No upstream catalog acceptance is implied.

## Findings, in priority order

### 1. High — rollback does not restore a coherent web/runtime release

Evidence: [install.sh](../scripts/install.sh#L46),
[rollback.sh](../scripts/rollback.sh#L9), [settings.php](../settings.php#L4).
Release snapshots include runtime code and web assets, but the PHP entry pages
remain in the moving Git checkout. Rollback switches `build/current`; it does
not restore those PHP pages. Failed activation uses the same partial restoration.

Reproduced locally by serving the summary JavaScript from commit `6402770` with
the current Config PHP fragment. That is the combination a rollback across the
Config-title removal can produce. Browser errors were:
`Cannot read properties of null (reading 'before')` and
`wledSummaryPreview is not defined`. The old script expects a heading that the
new PHP removes. This was a controlled historical-version simulation, not a
rollback of the live FPP04 device.

Recommendation: version PHP entry pages, assets, runtime and adapter as one
release, or make stable PHP dispatchers load the selected release. Add an
upgrade/failure/rollback test that loads Config and WLED in a browser. Also
validate settings-format compatibility before selecting an older release.

### 2. High — FPP layout import bypasses the supported data interface

Evidence: [layout.py](../runtime/layout.py#L15) directly reads
`config/model-overlays.json` and `config/co-pixelStrings.json`. Both ordinary
import and the virtual-layout workflow depend on these records.

This is a direct gap against guide section 3.4. It can miss live changes and is
coupled to internal file formats. It is read-only, so this finding does not mean
the importer corrupts FPP's files.

Recommendation: fetch models and channel-output data through FPP's documented
HTTP APIs, with bounded requests, explicit errors, and tests against the actual
FPP 10 response structures. Keep importing and previewing separate from changes
to the user's saved plugin layout.

### 3. Medium — an Apache error can prevent the rest of uninstall

Evidence: [fpp_uninstall.sh](../scripts/fpp_uninstall.sh#L2) enables `set -e`, then
calls web removal on line 5 before stopping the runtime. The called
[configure-web.sh](../scripts/configure-web.sh#L24) exits nonzero if Apache's
configuration test or reload fails. An unrelated invalid Apache configuration
can therefore prevent service, unit and socket cleanup from running.

This is a source-confirmed failure path; it was not induced on FPP04. The
successful/idempotent cleanup tests do not prove cleanup after that failure.

Recommendation: attempt independent cleanup steps even when one fails, preserve
useful diagnostics, and report failure after all safe cleanup has been attempted.
Add an injected Apache-failure uninstall test. This concerns guide section 2.1.

### 4. Medium — every update retains another full release indefinitely

Evidence: [install.sh](../scripts/install.sh#L46) creates a timestamped release
and changes `current` / `previous` links. Neither install nor rollback prunes
older release directories. Repeated development updates therefore accumulate
copies of the runtime, assets and native libraries on the controller's storage.

Recommendation: retain current, previous, and any still-in-use release; safely
remove unreferenced releases once their processes/mappings are no longer active.
Check available space before staging a release. Do not delete a library merely
because its release is no longer selected.

### 5. Medium — browser regressions are not covered by CI

Evidence: [verify.yml](../.github/workflows/verify.yml#L19) invokes
[scripts/verify.sh](../scripts/verify.sh#L7), which runs Python, C++ frame checks
and syntax checks. It does not execute the repository's `tests/browser_*.js`
workflows. Those tests are currently run manually through the browser CLI.

Consequently, a green CI result can coexist with broken navigation, stale
controls, a theme regression or the rollback failure above.

Recommendation: add a repeatable browser-test runner with isolated fixtures to
CI, covering Config, wrapped WLED, authorization, layout editing, previews,
mobile widths and light/dark/auto. Include the historical rollback reproduction.

## Areas with positive evidence

| Area | Observed implementation |
| --- | --- |
| Metadata | Validates against the current official `pluginInfo.schema.json`; resource and Raspberry Pi restrictions are present. |
| Output isolation | Rendering and network work run outside FPP's output thread; the channel hook uses a try-lock, bounded validated frames and stale-frame rejection. |
| Ownership | Show locks, overlapping sources, quiet periods, runtime failure and stale observer behavior have automated tests. |
| Persistence | JSON saves use temporary files, atomic replacement and fsync; malformed input is validated and several failed mutations are tested as atomic. |
| FPP lifecycle | Root Makefile includes FPP's shared setup; builds occur during installation. FPP restarts are requested through its flag, not executed directly. |
| Logs and permissions | One FPP-resolved append-only runtime log; service runs as `fpp`, with systemd filesystem restrictions and bounded tasks/memory. |
| UI integration | Shared FPP wrapper/navigation, logo, semantic colors, browser-persistent theme choice, and verified 320/390/1280px layouts on the recently changed routes. |
| Network and API | Request/body limits, worker limits, socket permissions, authorization checks and native-device realtime safeguards are present. |

These observations are not a penetration test, formal concurrency proof, or a
claim that every current feature has passed hardware acceptance.

## Maintainability and acceptance work

The hand-written Python and JavaScript mix clear modules with dense, multi-action
one-line functions. `web/settings.html` still embeds significant application
logic; its extraction by PHP depends on document structure. Moving that logic to
modules and enforcing formatter/linter rules would make review and regression
prevention easier. Preserve behavior with meaningful workflow tests while doing so.

The native adapter intentionally keeps its library mapping resident because FPP
may retain command Result objects. It does not claim unload support. Its
`shutdown()` also joins the worker synchronously. Revisit result ownership and
asynchronous shutdown before opting into unload; this is not evidence of a
currently observed use-after-free.

Pi 4/5 workload limits, direct-to-device mixed-routing shows, repeated physical
handoff/resume, and native receiver firmware behavior remain hardware acceptance
gates. The new node code 127 is a private fork extension, not an upstream allocation.
No receiving ESP controller was flashed during this work.

## Verification completed for this review/change

- `bash scripts/verify.sh`: passed all **152 Python tests**, C++ frame checks under
  AddressSanitizer/UndefinedBehaviorSanitizer, Python compilation and shell syntax.
- Current official FPP metadata schema: passed.
- WLED receiver fork: web asset build, **16 existing Node tests**, **2 new lookup
  tests**, and `pio run -e esp32dev` passed. Generic build uses 81,536 bytes RAM
  and 1,298,141 bytes flash; that binary is not universal for other boards.
- Browser node-list test: FPP type 127 and ESP32 labels pass; type 0 stays unknown.
- FPP04: plugin updated; FPP identity, installed lookup and healthy observer/runtime
  checked. No lighting commands or receiver flashing were performed for this check.
- Controlled rollback UI simulation: reproduced the failure in finding 1.

Suggested repair order: coherent rollback, API-backed FPP layout reads, resilient
uninstall, release retention, then automated browser coverage. Re-run the audit
and complete hardware acceptance before changing the release stage.
