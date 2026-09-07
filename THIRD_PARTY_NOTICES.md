# Third-party notices

This integration is licensed under the EUPL 1.2 or later, matching WLED. See `LICENSE`. New integration code is Copyright (c) 2026 stingerman1 and contributors. The upstream copyright statements in `LICENSE` and copied source files remain intact.

| Component | Source and license |
|---|---|
| WLED engine, palettes, math, fonts and main web UI | [WLED v16.0.1](https://github.com/wled/WLED/tree/v16.0.1), EUPL 1.2 or later, Christian Schwinne and individual WLED contributors. Exact commit in `upstream.lock.json`. |
| WS2812FX ancestry | Harm Aldick, 2016; original MIT notice in `licenses/WS2812FX-MIT.txt`; WLED's derived engine retains its EUPL notices. |
| FastLED slim and derived math/color functions | FastLED contributors, modified by dedehai; MIT, `licenses/FastLED-MIT.txt`. Source headers include additional individual attributions. |
| iro.js 5.5.2 | James Daniel, MPL 2.0, `licenses/iro-MPL-2.0.txt`; [original source](https://github.com/jaames/iro.js/tree/v5.5.2). Distributed browser file is unmodified. |
| RangeTouch 2.0.1 | Sam Potts, MIT, `licenses/RangeTouch-MIT.md`; [original source](https://github.com/sampotts/rangetouch/tree/v2.0.1). |
| FPP integration headers/library | [FalconChristmas/fpp](https://github.com/FalconChristmas/fpp); installed system dependency. The plugin builds against the installed FPP headers and does not redistribute/replace FPP binaries. |
| Paho MQTT 2.1.0 | Eclipse Paho, EPL 2.0 / EDL 1.0; installed separately from the Python distribution, retaining its license metadata. |
| python-zeroconf 0.148.0 | Zeroconf contributors, LGPL 2.1 or later; installed separately with its distribution license metadata. |
| ifaddr 0.2.0 | ifaddr contributors, MIT; installed dependency. |
| async-timeout 5.0.1 | aio-libs contributors, Apache 2.0; installed dependency. |
| Astral 3.2 | Simon Kennedy, Apache 2.0; [source and documentation](https://github.com/sffjunkie/astral). Installed dependency with retained license metadata; computes solar events locally. |

Embedded font source headers and their attribution comments are copied intact from the pinned WLED tree. No third-party trademark endorsement is implied. Include this file, `LICENSE`, `licenses/`, the complete corresponding upstream source and all dependency license metadata when distributing binary release bundles. Dependency redistribution review and final binary release packaging remain alpha release gates.

The Linux preparation step makes explicit adaptations to WLED: virtual bus initialization, filesystem-map/custom-palette/font substitutions, pointer-width-safe palette reads, Linux platform wrappers, extraction of existing math helpers, and two browser integration changes (WebSocket port preservation and removal of embedded update checking). Generated files retain upstream headers and are reproducible from the pinned source plus this repository; they are not checked in.
