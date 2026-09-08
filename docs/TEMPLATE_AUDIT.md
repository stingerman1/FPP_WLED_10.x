# FPP template conformance audit

Reviewed September 8, 2026 against FalconChristmas/fpp-plugin-Template commit
`5c0dc73545f5e032902135d8770b1599d489eabe`, specifically
[PLUGIN_GUIDELINES.md](https://github.com/FalconChristmas/fpp-plugin-Template/blob/5c0dc73545f5e032902135d8770b1599d489eabe/PLUGIN_GUIDELINES.md),
[PLUGININFO_FORMAT.md](https://github.com/FalconChristmas/fpp-plugin-Template/blob/5c0dc73545f5e032902135d8770b1599d489eabe/PLUGININFO_FORMAT.md), and its JSON schema.

**Result: metadata validates, but the plugin does not yet fully conform to the guidelines.**
This is a source audit, not catalog approval. The template itself is an example;
its documented guidelines take precedence over copying every sample file.

| Area | Finding |
| --- | --- |
| Metadata | PASS: official Draft 2020-12 JSON schema validation, repository identity, required fields, compatibility range, resource hints. Added Raspberry Pi platform restriction to match the actual installer and a documentation link. x64 CI exercises portable code; the installer still targets Pi 4/5 64-bit. |
| Lifecycle entry points | PASS: fpp_install, fpp_uninstall and callbacks exist; upgrades use FPP's fallback to fpp_install. C++ builds during installation rather than an FPP start hook. |
| Repeated installation | Staged release activation and rollback are implemented and tested. Real full upgrade succeeded on stock Pi FPP 10. |
| Uninstall | PARTIAL: service, tmpfiles declaration and Apache include are removed; plugin-owned persistent state is deliberately retained. Complete removal conflicts with the current preservation policy and needs an explicit documented reset/removal workflow. Installed uninstall-twice testing remains outstanding. |
| Logging (§1) | GAP: Python logs/uncaught errors currently go to systemd's journal. Route them to the single FPP-resolved `plugin-FPP_WLED_10.x.log`, with append semantics and FPP rotation. |
| Privilege use (§2.4) | FIXED: replaced install-time sudo with runuser for the intentionally unprivileged validation step. No broad world-writable permissions. |
| FPP core-upgrade rebuild (§2.7/2.9) | GAP: shell build exists, but no root Makefile using FPP's common setup. Core upgrades cannot discover our build through the documented Makefile mechanism. |
| Native unload (§2.9) | PARTIAL: shutdown removes/deletes commands, joins the bounded worker and returns command-drain readiness; these APIs exist in the pinned FPP 10 headers. The library intentionally does not opt into dlclose because FPP can retain asynchronous Result objects. Do not claim hot binary replacement or add the opt-in until result lifetimes are proven safe. |
| Core interaction (§3/4) | Uses FPP channel/plugin APIs and does not edit core channel configuration. No production plugin script reboots/restarts fppd. Runtime restart is its own service. Adapter replacement still tells users to restart FPP instead of setting the documented restart flag. |
| Filesystem (§3.5/5) | GAP: plugin data is a directory under config/plugin.FPP_WLED_10.x rather than data under plugindata. Several paths assume /home/fpp/media. Migration must preserve tokens, presets, ownership locks and rollback. External service/Apache/run paths also need a complete declared inventory. |
| Dependencies (§6) | GAP versus current guidance: pinned pip packages use per-release private virtual environments; template recommends system Python/dependencies.python. Changing this needs dependency-conflict and rollback testing, not a superficial path substitution. dependencies metadata itself is optional in 2026. |
| UI (§8) | GAP: the FPP landing page inherits FPP styles, but standalone WLED/Settings uses a fixed dark palette and custom forms. Full light/dark and 320px acceptance has not passed. Lighting swatch colors are functional data; layout/theming must still comply. |
| Menu (§9) | PASS: one Output menu entry. |
| License/resource hints | PASS: root license and third-party notices; RAM/core hints present. |
| Monetization/telemetry/advertising (§10–13) | No plugin-owned monetization, analytics or tunnel dependency. Upstream WLED assets are shipped too: a full generated-asset link review is still required before claiming these clauses pass for the entire distribution. |

## Recommended conformance sequence

1. Add FPP-resolved logging and paths; migrate data with restart/rollback tests.
2. Add a root FPP-compatible Makefile and rebuild/ABI checks for core upgrades.
3. Implement a supported adapter lifecycle and restart-flag workflow against stock FPP 10.
4. Align dependency installation and uninstall/reset semantics without losing user state.
5. Integrate Settings with FPP theme/layout helpers; verify every page in both themes and at phone widths; review generated upstream assets for prohibited links.

Keep this audit in the plugin's documentation. Do not copy the template's guideline/format files into this repository: the template asks those shared documents to remain upstream.
