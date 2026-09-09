<?php
// A fragment inside FPP's normal wrapper: retain its theme, Bootstrap and menu.
$markup = file_get_contents(__DIR__ . '/web/settings.html');
$markup = substr($markup, strpos($markup, '<h1>'));
$markup = str_replace('</body></html>', '', $markup);
$markup = preg_replace('/<script src="([^":]+)"/', '<script src="/fpp-wled/$1"', $markup);
$markup = str_replace(['href="./"', 'href="presets.json"'], ['href="/fpp-wled/"', 'href="/fpp-wled/presets.json"'], $markup);
$markup = preg_replace('/<button(?![^>]*\bclass=)/', '<button class="btn btn-outline-primary"', $markup);
$markup = preg_replace('/<textarea(?![^>]*\bclass=)/', '<textarea class="form-control"', $markup);
$markup = preg_replace('/<select(?![^>]*\bclass=)/', '<select class="form-select"', $markup);
$markup = preg_replace_callback('/<input\b[^>]*>/', function ($match) {
    $class = strpos($match[0], 'type="checkbox"') !== false ? 'form-check-input' : 'form-control';
    if (strpos($match[0], 'type="range"') !== false) $class = 'form-range';
    return str_replace('<input', '<input class="' . $class . '"', $match[0]);
}, $markup);
?>
<link rel="stylesheet" href="/fpp-wled/settings.css">
<div class="fpp-wled container-fluid px-0" id="fpp-wled-settings"><?php echo $markup; ?></div>
