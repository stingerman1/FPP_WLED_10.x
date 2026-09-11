# WLED navigation

The FPP plugin entry opens Config until background lighting has been enabled for
the first time. After that it opens WLED. The completion flag lives in the device's
ownership file and survives disabling ambient lighting or restarting. Existing
installations with background lighting enabled are treated as already configured.

WLED and Config have matching icon links using the same browser tab. Explicitly
choosing WLED from Config is allowed before finishing setup, without a redirect
loop. Opening Config directly always stays on Config. Both destinations now use
FPP's `plugin.php` wrapper: `lights.php` hosts the WLED controls in an isolated
same-origin frame, and `settings.php` contains the config fragment. FPP's header,
menus and footer remain in the outer page. Shared navigation displays the existing
Pixel Monkey logo, also used on plugin details and credits.

The plugin header offers Light, Dark and Auto. The browser remembers one choice
across Config, WLED and plugin details. Explicit Light/Dark choices apply to the
whole wrapped page; Auto follows FPP's host theme. Standalone Auto follows the
system color scheme. This preference does not write FPP's global settings.
The embedded WLED frame inherits the outer page's semantic colors and hides its
own appearance control. All three choices are visible buttons, with one selected.

The status notice, access prompt and WLED bottom navigation share one fixed
footer. A ResizeObserver reserves their combined height in the scrolling content,
including wrapped messages, so controls remain above the footer.

Plugin details and maintenance remain available from Config, or via the plugin
entry URL with `&manage=1`. Runtime failures keep the entry page's troubleshooting
information visible rather than redirecting to a broken page.

Tooltips use viewport coordinates, move below controls near the top edge and
stay inside the left/right edges. Browser checks cover first-use routing,
configured-device routing, both navigation directions and 390/1280px tooltips.

Config shows a read-only lighting summary. Use WLED for power, brightness,
effects, palettes and color selection. The live pixel preview starts off on every
page load. Its single Enable/Disable button affects this browser's preview only,
not lighting output. While off it makes no preview requests and does not draw
frames. While enabled it requests the next frame 500 ms after the previous
request completes; hidden tabs pause preview requests. Disabling aborts any
pending request and discards late replies. The lighter status summary remains
available, polling every two seconds while visible. The one-time nightlight
timer remains in a collapsed section, opened directly by WLED's Timer button.

Plugin Manager and plugin headings identify the release as `0.1.0-alpha.2`
instead of the unnumbered “experimental alpha” label. Use numbered `-alpha.N`
and `-beta.N` labels during those stages. Production titles use increasing major
build numbers (`1`, `2`, …) with no prerelease label. Update the displayed label
in `pluginInfo.json`, `plugin.php` and `web/settings.html` together when releasing;
the upstream WLED engine version in the summary is a separate version.
