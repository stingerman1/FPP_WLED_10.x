<h2>WLED for FPP &middot; Linux alpha</h2>
<?php if (PHP_INT_SIZE !== 8): ?>
<p role="alert"><strong>This FPP web environment is 32-bit.</strong> This plugin requires a fully 64-bit FPP installation. A 64-bit Pi or kernel alone is not sufficient. The runtime cannot be installed on this environment; changing ports or reinstalling the plugin will not resolve it.</p>
<p>Check <a href="/api/file/logs/fpp_plugin_manager.log" target="_blank" rel="noopener">the plugin installation log</a> for the build failure. Back up FPP configuration before planning an OS migration.</p>
<?php return; endif; ?>
<p>Ambient lighting yields to FPP shows. Direct-to-device shows need explicit Show Start and Show End hooks.</p>
<p><a href="/fpp-wled/" target="_blank" rel="noopener">Open WLED runtime</a> · <a href="/fpp-wled/settings" target="_blank" rel="noopener">Setup and compatibility</a></p>
<p>This alpha requires Raspberry Pi 4/5 hardware acceptance. FPP's built-in WLED interface remains separate.</p>
<p id="wled-web-status" role="status">Checking WLED web access...</p>
<section aria-labelledby="wled-token-heading">
<h3 id="wled-token-heading">Runtime access</h3>
<p>The runtime token authorizes lighting, preset and configuration changes. The button below retrieves the existing token; it does not replace it. Anyone with access to this FPP page can retrieve it, so keep FPP access limited to trusted users.</p>
<button type="button" id="wled-get-token">Get runtime token</button>
<div id="wled-token-result" hidden>
    <p><label>API token <input id="wled-token-value" type="password" readonly autocomplete="off" spellcheck="false" size="44" style="max-width:100%;box-sizing:border-box"></label></p>
    <button type="button" id="wled-show-token">Show token</button>
    <button type="button" id="wled-copy-token">Copy token</button>
    <button type="button" id="wled-token-login">Log in to runtime</button>
    <button type="button" id="wled-clear-token">Clear from page</button>
</div>
<p id="wled-token-status" role="status" aria-live="polite"></p>
</section>
<script src="plugin.php?plugin=FPP_WLED_10.x&amp;file=web/token-access.js&amp;nopage=1"></script>
<script>
(() => {
    const status = document.getElementById('wled-web-status');
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    fetch('/fpp-wled/api/status', {signal: controller.signal, cache: 'no-store'})
        .then(async response => {
            if (response.status === 404) {
                throw Error('The WLED web route is missing. Update/reinstall this plugin and check the installation log for errors. Restarting FPP alone does not install the route.');
            }
            if (!response.ok) throw Error('WLED runtime unavailable (HTTP ' + response.status + '). Check the fpp-wled service and installation log.');
            await response.json();
            status.textContent = 'WLED web access is ready on this FPP address and port.';
        })
        .catch(error => { status.textContent = error.name === 'AbortError' ? 'WLED web access timed out. Check the fpp-wled service and installation log.' : error.message; })
        .finally(() => clearTimeout(timeout));
})();
</script>
