# FPP template conformance follow-up

Reviewed against FalconChristmas/fpp-plugin-Template commit `5c0dc73545f5e032902135d8770b1599d489eabe` and its [guidelines](https://github.com/FalconChristmas/fpp-plugin-Template/blob/5c0dc73545f5e032902135d8770b1599d489eabe/PLUGIN_GUIDELINES.md) and metadata schema.

This is a project conformance review, not upstream catalog approval or physical lighting acceptance. The earlier UI assessment was too broad: standalone WLED navigation and fixed plugin colors did not provide the same FPP-native experience as the config wrapper. The 2026-09-11 correction keeps both main pages wrapped, scopes config styling, uses semantic UI colors and preserves the host theme. See NAVIGATION.md; this does not certify unrelated requirements added to upstream guidelines since the pinned audit.

| Area | Implementation and evidence |
| --- | --- |
| Metadata | Official JSON schema passes. Pi platform restriction, RAM/core hints, documentation link and actual apt/Python dependencies are declared. |
| Logging | FPP common resolves LOGDIR. The service and launcher append Python/native diagnostics to plugin-FPP_WLED_10.x.log. No custom rotation or truncate-on-start. Repeated-launch test confirms one shared append-only log. |
| Lifecycle | Install and uninstall hooks remain fast where required; compilation occurs at installation. A root Makefile includes FPP common setup for core-upgrade rebuilds and validates ABI before publishing the loader binary. |
| Native lifetime | Shutdown withdraws/deletes commands and drains pending work. The mapping deliberately remains resident because FPP can retain Result objects. Unload opt-in is optional in the template; it is not falsely claimed. Build checks confirm no GNU-unique symbols. |
| Restart handling | Install and rollback set FPP's restartFlag through its shell helper. No direct fppd restart or device reboot. Users may defer the requested restart around shows. |
| Paths/data | FPP common resolves relocated media paths. Standard plugin settings register the data directory through WriteSettingToFile. Structured JSON data moves intact to plugindata/FPP_WLED_10.x. Migration tests cover tokens, locks, presets, permissions, repeated installs and conflicts. |
| Dependencies | System Python with declared dependencies and pip --break-system-packages. No newly created private virtual environments or alternate package managers. Exact versions match the tested reproducible runtime requirements. Previous release directories remain available for rollback. |
| Removal | Uninstall removes the service, tmpfiles declaration, Apache include/enabled link and named runtime sockets. Isolated cleanup tests run twice. User data is preserved by default as requested; an explicit FPP settings checkbox opts into permanent data removal at uninstall. Purge tests confirm idempotence and confinement. FPP retains its managed support log. |
| UI | Settings is a fragment in FPP's normal wrapper, with Bootstrap controls and semantic theme variables. Direct runtime access follows FPP/OS color scheme. Upstream WLED chrome uses semantic system colors; lighting swatches remain actual color data. Chromium checks cover light/dark themes and 320px width without horizontal scrolling. |
| Menu | One Status/Control entry and one Input/Output Setup entry, with the template rendering loop. Regression checks execute menu.inc for each FPP section. |
| Host boundaries | Plugin APIs/channel hooks, no edits to core channel configuration, no direct FPP internal HTTP port, no piped remote execution. Privilege dropping uses runuser during validation. |
| License/links | Root license/notices retained. Generated UI and plugin-owned source reviewed for donation/monetization/analytics links; no such integration is enabled. No tunnel or advertising dependency. |

## Declared filesystem effects

- Plugin repository and staged builds under FPP's PLUGINDIR/FPP_WLED_10.x.
- Plugin settings: MEDIADIR/config/plugin.FPP_WLED_10.x, through FPP's helper.
- Structured runtime data: MEDIADIR/plugindata/FPP_WLED_10.x.
- FPP-managed log: LOGDIR/plugin-FPP_WLED_10.x.log.
- Plugin-owned service and tmpfiles files: /etc/systemd/system/fpp-wled.service and /etc/tmpfiles.d/fpp-wled.conf.
- Plugin-owned Apache include/link: /etc/apache2/conf-available/fpp-wled.conf and conf-enabled/fpp-wled.conf.
- Runtime sockets/lock: /run/fpp-wled. Netlink is allowed for Linux interface enumeration; physical outputs remain owned by FPP.

Uninstall retains saved data unless the user selects deletion. This explicitly preserves the user's requested reinstall/rollback behavior; no silent deletion is presented as compliance. See [installation](INSTALL.md) for operation and removal details.
