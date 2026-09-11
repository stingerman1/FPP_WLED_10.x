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

The host theme controls both wrapped pages. A saved standalone WLED appearance
preference cannot override FPP. The frame observes host theme changes, uses its
semantic color variables and hides its independent theme toggle. Links to Config
from inside WLED navigate the outer page. Standalone access remains optional.

Plugin details and maintenance remain available from Config, or via the plugin
entry URL with `&manage=1`. Runtime failures keep the entry page's troubleshooting
information visible rather than redirecting to a broken page.

Tooltips use viewport coordinates, move below controls near the top edge and
stay inside the left/right edges. Browser checks cover first-use routing,
configured-device routing, both navigation directions and 390/1280px tooltips.
