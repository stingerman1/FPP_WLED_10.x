<?php
// Use the FPP plugin-settings helper; structured runtime data lives in plugindata.
// FPP's web configuration also renders page metadata when invoked by CLI.
$_SERVER['REQUEST_URI'] ??= '/plugin.php?plugin=FPP_WLED_10.x&page=plugin.php';
ob_start();
require_once (getenv('FPPDIR') ?: '/opt/fpp') . '/www/config.php';
require_once (getenv('FPPDIR') ?: '/opt/fpp') . '/www/common.php';
if (($argv[1] ?? '') === 'purge-requested') {
    LoadPluginSettings('FPP_WLED_10.x');
    $purge = ($pluginSettings['deleteDataOnUninstall'] ?? '0') === '1';
    ob_end_clean();
    echo $purge ? '1' : '0';
} else {
    WriteSettingToFile('dataDirectory', getenv('PLUGIN_STATE'), 'FPP_WLED_10.x');
    ob_end_clean();
}
?>
