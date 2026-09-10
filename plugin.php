<h2><img src="/api/plugin/FPP_WLED_10.x/icon" alt="" width="40" height="40" style="vertical-align:middle;margin-right:.5rem">WLED for FPP &middot; Linux alpha</h2>
<?php if (PHP_INT_SIZE !== 8): ?>
<p role="alert"><strong>This FPP web environment is 32-bit.</strong> This plugin requires a fully 64-bit FPP installation. A 64-bit Pi or kernel alone is not sufficient. The runtime cannot be installed on this environment; changing ports or reinstalling the plugin will not resolve it.</p>
<p>Check <a href="/api/file/logs/fpp_plugin_manager.log" target="_blank" rel="noopener">the plugin installation log</a> for the build failure. Back up FPP configuration before planning an OS migration.</p>
<?php return; endif; ?>
<p>Choose colors and patterns to play between your shows. FPP shows take priority, and your background lighting returns afterward.</p>
<p><a href="/fpp-wled/" target="_blank" rel="noopener">Open WLED lights</a> · <a href="plugin.php?plugin=FPP_WLED_10.x&amp;page=settings.php" target="_blank" rel="noopener">Settings and help</a></p>
<p><a href="plugin.php?plugin=FPP_WLED_10.x&amp;page=credits.php">Open-source credits and licenses</a></p>
<p>This is an early test version. Full testing on Raspberry Pi 4 and 5 is still needed.</p>
<p id="wled-web-status" role="status">Checking WLED web access...</p>
<section><h3>Lighting access</h3><p>Open WLED and choose <strong>Enable lighting controls</strong>. You can then change colors, save favorite looks and edit settings. This browser remembers your access. No code to copy or paste.</p><p><a href="plugin.php?plugin=FPP_WLED_10.x&amp;page=settings.php#runtime-access">Manage access in WLED settings</a></p><details><summary>Advanced: retrieve a token for an API client</summary><p>Only needed for external API clients or direct runtime access. Keep the token private.</p>
<p id="wled-saved-access" role="status"></p><button type="button" id="wled-get-token">Get API token</button><div id="wled-token-result" hidden><input id="wled-token-value" type="password" readonly aria-label="API token"><button id="wled-show-token">Show token</button><button id="wled-copy-token">Copy token</button><button id="wled-token-login">Save browser access</button><button id="wled-clear-token">Clear from page</button></div><p id="wled-token-status" role="status"></p></details></section>
<section class="border rounded p-3 my-3">
<h3>Removal preference</h3>
<p>Normally, removing this plugin keeps your token, presets and show locks for a later reinstall. Enable the option below only if you want those files permanently deleted when you uninstall.</p>
<?php if (function_exists('PrintSettingCheckbox')) PrintSettingCheckbox('Delete saved data when uninstalling', 'deleteDataOnUninstall', 0, 0, '1', '0', 'FPP_WLED_10.x'); ?>
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
