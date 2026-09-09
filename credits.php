<h2>Open-source credits and licenses</h2>
<p>Thank you to the authors and communities whose work makes WLED for FPP possible.</p>
<p><a href="plugin.php?plugin=FPP_WLED_10.x&amp;page=plugin.php">Back to WLED for FPP</a> &middot;
<a href="https://github.com/stingerman1/FPP_WLED_10.x/blob/main/THIRD_PARTY_NOTICES.md" target="_blank" rel="noopener">Browse linked credits and source repositories</a></p>
<?php
// Fixed local files only. Credits remain available without the runtime or Internet.
function fppWledCreditText($path) {
    echo '<pre class="border rounded p-3" style="white-space:pre-wrap;overflow-wrap:anywhere">';
    echo htmlspecialchars(file_get_contents($path), ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    echo '</pre>';
}
fppWledCreditText(__DIR__ . '/THIRD_PARTY_NOTICES.md');
foreach (array_merge([__DIR__ . '/LICENSE'], glob(__DIR__ . '/licenses/*')) as $creditFile) {
    if (!is_file($creditFile)) continue;
    echo '<details class="my-2"><summary>' . htmlspecialchars(basename($creditFile), ENT_QUOTES, 'UTF-8') . '</summary>';
    fppWledCreditText($creditFile);
    echo '</details>';
}
?>
