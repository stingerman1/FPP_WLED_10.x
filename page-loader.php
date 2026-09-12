<?php
// Stable FPP entry point: PHP and runtime assets come from the same release.
$wledRoot = __DIR__;
// Long-lived PHP workers may cache the old symlink target across an upgrade.
clearstatcache(true);
$wledRelease = realpath($wledRoot . '/build/current');
$wledReleases = realpath($wledRoot . '/build/releases');
if (!in_array($wledPage ?? '', ['plugin.php', 'settings.php', 'lights.php', 'credits.php', 'navigation.php', 'runtime-token.php'], true)) {
    http_response_code(404);
    return;
}
if ($wledRelease !== false) {
    if (!$wledReleases || strpos($wledRelease, $wledReleases . DIRECTORY_SEPARATOR) !== 0) {
        http_response_code(503);
        echo 'Invalid WLED release. Reinstall the plugin from FPP.';
        return;
    }
    if (is_file($wledRelease . '/pages/' . $wledPage)) {
        require $wledRelease . '/pages/' . $wledPage;
        return;
    }
    if (is_file($wledRelease . '/release.json')) {
        http_response_code(503);
        echo 'Incomplete WLED release. Reinstall the plugin from FPP.';
        return;
    }
    // Migration only: old releases contain complete standalone HTML, but no PHP.
    // Embed that HTML intact rather than combining it with a newer PHP fragment.
    if (in_array($wledPage, ['plugin.php', 'settings.php', 'lights.php'], true)) {
        $wledLegacyPath = $wledPage === 'settings.php' ? '/fpp-wled/settings' : '/fpp-wled/?view=lights';
        echo '<p class="text-body-secondary">Previous WLED release. Complete the plugin update to use the new configuration page.</p>';
        echo '<iframe title="WLED previous release" class="w-100 border rounded" style="height:80dvh;min-height:36rem" src="' . htmlspecialchars($wledLegacyPath, ENT_QUOTES, 'UTF-8') . '"></iframe>';
        return;
    }
}
// Source-tree development, initial installation, and the stable legacy access bridge.
require $wledRoot . '/pages/' . $wledPage;
