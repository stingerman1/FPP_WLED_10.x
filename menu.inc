<?php
// FPP includes this file once per menu section; metadata readers also inspect the array.
$menuEntries = [
    ['text' => 'WLED for FPP', 'type' => 'status', 'page' => 'plugin.php', 'wrap' => 1],
    ['text' => 'WLED Setup', 'type' => 'output', 'page' => 'settings.php', 'wrap' => 1]
];
if (isset($menu, $plugin)) {
    foreach ($menuEntries as $entry) {
        if ($entry['type'] !== $menu) continue;
        $url = 'plugin.php?plugin=' . rawurlencode($plugin) . '&page=' . rawurlencode($entry['page']);
        echo '<li><a href="' . htmlspecialchars($url, ENT_QUOTES, 'UTF-8') . '">'
            . htmlspecialchars($entry['text'], ENT_QUOTES, 'UTF-8') . '</a></li>' . "\n";
    }
}
?>
