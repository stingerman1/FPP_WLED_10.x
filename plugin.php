<?php
$port = 8787;
$path = '/home/fpp/media/config/plugin.FPP_WLED_10.x/config.json';
if (is_readable($path)) {
    $config = json_decode(file_get_contents($path), true);
    if (is_int($config['port'] ?? null) && $config['port'] >= 1024 && $config['port'] <= 65535) $port = $config['port'];
}
?>
<h2>WLED for FPP · Linux alpha</h2>
<p>Ambient lighting yields to FPP shows. Direct-to-device shows need explicit Show Start and Show End hooks.</p>
<p><a id="wled-runtime" target="_blank" rel="noopener">Open WLED runtime</a> · <a id="wled-setup" target="_blank" rel="noopener">Setup and compatibility</a></p>
<p>This alpha requires Raspberry Pi 4/5 hardware acceptance. FPP's built-in WLED interface remains separate.</p>
<script>
{ const base=new URL(window.location.href);base.protocol='http:';base.port=<?= json_encode($port) ?>;base.pathname='/';base.search='';base.hash='';document.getElementById('wled-runtime').href=base.href;base.pathname='/settings';document.getElementById('wled-setup').href=base.href; }
</script>
