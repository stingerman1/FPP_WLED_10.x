<?php $wledCurrent = 'lights'; require __DIR__ . '/navigation.php'; ?>
<div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-2">
  <span class="text-body-secondary">Lighting controls. FPP shows take priority.</span>
  <a href="/fpp-wled/?view=lights" target="_blank" rel="noopener">Open standalone WLED</a>
</div>
<iframe id="fpp-wled-frame" title="WLED lighting controls" src="/fpp-wled/?view=lights&amp;embedded=1" class="w-100 border rounded bg-body" style="height:80dvh;min-height:36rem;display:block"></iframe>
<p class="text-body-secondary mt-2">If lighting controls are unavailable, open Config to check access and runtime status.</p>
