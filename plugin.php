<h2>WLED for FPP · Linux alpha</h2>
<p>Ambient lighting yields to FPP shows. Direct-to-device shows need explicit Show Start and Show End hooks.</p>
<p><a href="/fpp-wled/" target="_blank" rel="noopener">Open WLED runtime</a> · <a href="/fpp-wled/settings" target="_blank" rel="noopener">Setup and compatibility</a></p>
<p>This alpha requires Raspberry Pi 4/5 hardware acceptance. FPP's built-in WLED interface remains separate.</p>
<p id="wled-web-status" role="status">Checking WLED web access...</p>
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
