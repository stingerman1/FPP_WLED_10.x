<?php $wledCurrent = $wledCurrent ?? ''; ?>
<nav class="d-flex flex-wrap align-items-center gap-2 border rounded bg-body-tertiary p-2 mb-3" aria-label="WLED pages" id="fpp-wled-page-navigation">
  <img src="/api/plugin/FPP_WLED_10.x/icon" alt="Pixel Monkey" style="width:2.5rem;height:2.5rem;object-fit:contain">
  <a id="wled-navigation" class="btn <?= $wledCurrent === 'lights' ? 'btn-primary' : 'btn-outline-primary' ?> d-inline-flex align-items-center gap-2" href="plugin.php?plugin=FPP_WLED_10.x&amp;page=lights.php" <?= $wledCurrent === 'lights' ? 'aria-current="page"' : '' ?>>
    <svg viewBox="0 0 24 24" style="width:1.5rem;height:1.5rem" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" d="M9 18h6m-6 3h6M8 14a6 6 0 1 1 8 0c-1 1-1 2-1 2H9s0-1-1-2Z"/></svg>WLED
  </a>
  <a id="wled-config-navigation" class="btn <?= $wledCurrent === 'config' ? 'btn-primary' : 'btn-outline-primary' ?> d-inline-flex align-items-center gap-2" href="plugin.php?plugin=FPP_WLED_10.x&amp;page=settings.php" <?= $wledCurrent === 'config' ? 'aria-current="page"' : '' ?>>
    <svg viewBox="0 0 24 24" style="width:1.5rem;height:1.5rem" aria-hidden="true"><g fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/><path d="M12 2v4m0 12v4M2 12h4m12 0h4M5 5l3 3m8 8 3 3M5 19l3-3M16 8l3-3"/></g></svg>Config
  </a>
  <a class="btn btn-outline-secondary" href="plugin.php?plugin=FPP_WLED_10.x&amp;page=plugin.php&amp;manage=1">Plugin details</a>
</nav>
