# Browser regression checks

On Linux, after installing the Python requirements and building the renderer:

```sh
npm ci
npx playwright install --with-deps chromium
npm run test:browser
```

The runner uses a new temporary runtime state directory and browser context for each scenario. The fake FPP observer and model API do not require a physical controller. Ports 18787, 18789 and 18890 must be available. PHP CLI is required. Browser navigation is restricted to loopback hosts; no live device is used. Test credentials are synthetic and never installed on FPP.

Coverage includes FPP-wrapped navigation, mobile light/dark/auto, read-only summary and opt-in preview, configuration workflows, editable segment fields, authorized API layout previews, UDP-discovery opt-in persistence, node labels, and matching PHP/asset selection across rollback. The rollback fixture reproduces the old heading-dependent script against its own versioned page, then switches both versions through the production dispatcher.

CI runs these checks on Ubuntu x64 and uploads traces and failure screenshots from `build/browser-results`. Python/native checks also run on ARM. These fixtures do not replace Pi performance, physical output, or real Apache lifecycle acceptance.
