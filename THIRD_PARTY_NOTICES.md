# Third-party notices

This integration is licensed under the EUPL 1.2 or later, matching WLED. See `LICENSE`. New integration code is Copyright (c) 2026 stingerman1 and contributors. The upstream copyright statements in `LICENSE` and copied source files remain intact.

| Component | Source and license |
|---|---|
| WLED engine, palettes, math, fonts and main web UI | [WLED v16.0.1](https://github.com/wled/WLED/tree/v16.0.1), EUPL 1.2 or later, Christian Schwinne and individual WLED contributors. Exact commit in `upstream.lock.json`. |
| WS2812FX ancestry | Harm Aldick, 2016; original MIT notice in `licenses/WS2812FX-MIT.txt`; WLED's derived engine retains its EUPL notices. |
| FastLED slim and derived math/color functions | FastLED contributors, modified by dedehai; MIT, `licenses/FastLED-MIT.txt`. Source headers include additional individual attributions. |
| iro.js 5.5.2 | James Daniel, MPL 2.0, `licenses/iro-MPL-2.0.txt`; [original source](https://github.com/jaames/iro.js/tree/1825363da88e1971befb6c6b827951594f388798). Distributed browser file is unmodified. |
| RangeTouch 2.0.1 | Sam Potts, MIT, `licenses/RangeTouch-MIT.md`; [original source](https://github.com/sampotts/rangetouch/tree/v2.0.1). |
| FPP integration headers/library | [FalconChristmas/fpp](https://github.com/FalconChristmas/fpp); installed system dependency. The plugin builds against the installed FPP headers and does not redistribute/replace FPP binaries. |
| Paho MQTT 2.1.0 | Eclipse Paho, EPL 2.0 / EDL 1.0; installed separately from the Python distribution, retaining its license metadata. |
| python-zeroconf 0.148.0 | Zeroconf contributors, LGPL 2.1 or later; installed separately with its distribution license metadata. |
| ifaddr 0.2.0 | ifaddr contributors, MIT; installed dependency. |
| async-timeout 5.0.1 | aio-libs contributors, Apache 2.0; installed dependency. |
| Astral 3.2 | Simon Kennedy, Apache 2.0; [source and documentation](https://github.com/sffjunkie/astral). Installed dependency with retained license metadata; computes solar events locally. |

## Additional bundled and derived credits

- **Preact**: Jason Miller and contributors, MIT; embedded in the upstream iro.js browser bundle. See [Preact source](https://github.com/preactjs/preact) and `licenses/Preact-MIT.txt`. iro.js declares Preact `^10.0.0`; the exact embedded patch version is not recorded in the WLED asset, so we do not claim one. The license copy comes from Preact 10.5.13.
- **iro-core**: James Daniel, MPL 2.0, the color manipulation component used by iro.js; see [source](https://github.com/irojs/iro-core) and `licenses/iro-core-license.txt`. iro.js declares `^1.2.1`; the license copy is from the 1.2.1 package.
- **WLED particle systems**: Copyright (c) 2024 Damian Schneider, EUPL 1.2 or later. The source headers and individual effect credits remain intact.
- **FastLED effects, palettes and helpers**: Daniel Garcia, Mark Kriegsman, FastLED contributors and WLED contributors including dedehai. In addition to fastled_slim, WLED identifies helpers derived from FastLED 3.6.0 in `colors.cpp`, `palettes.cpp` and `util.cpp`. The generated Linux utility source identifies this MIT ancestry.
- **Bitmap fonts**: c64esque by Nimble Beasts Collective, TinyUnicode and 6x13 from IT-Studio-Rech/bdf-fonts, Tom Thumb by Brian Swetland and Robey Pointer, and console raster fonts from idispatch/raster-fonts. WLED credits modifications to dedehai. Original header statements and source links are reproduced in `licenses/WLED-font-credits.txt`; the original headers are also preserved in prepared source.
- **WIcons**: the icon font embedded in WLED's `index.css`, maintained in the pinned WLED `wled00/data/icons-ui` directory and assembled with IcoMoon. The upstream selection and generation instructions are retained in the pinned source. Individual icon provenance still needs clarification; see the review notes below.
- **Other effect and math contributors**: the pinned WLED sources credit individual authors and linked algorithm sources beside their implementations. These comments remain part of the corresponding source; this summary does not replace them. See [WLED contributors](https://github.com/wled/WLED/graphs/contributors) and [pinned rendering source](https://github.com/wled/WLED/tree/29b389df1c1aaec6ff53aea742d17063b985906c/wled00).

## Installed runtime dependency license copies

These unmodified packages are installed from `requirements.txt`. Copies below supplement, and do not replace, their installed distribution metadata.

| Package | Credited authors | Local license text | Source |
|---|---|---|---|
| paho-mqtt 2.1.0 | Roger Light and others; Eclipse Paho contributors | `licenses/Paho-license-notice.txt`, `licenses/Paho-EPL-2.0.txt`, `licenses/Paho-EDL-1.0.txt` | [v2.1.0](https://github.com/eclipse-paho/paho.mqtt.python/tree/v2.1.0) |
| zeroconf 0.148.0 | Paul Scott-Murphy and python-zeroconf contributors | `licenses/zeroconf-LGPL.txt` (LGPL 2.1 or later) | [0.148.0](https://github.com/python-zeroconf/python-zeroconf/tree/0.148.0) |
| ifaddr 0.2.0 | Stefan C. Mueller and contributors | `licenses/ifaddr-MIT.txt` | [project](https://github.com/pydron/ifaddr) |
| async-timeout 5.0.1 | Andrew Svetlov and aio-libs contributors | `licenses/async-timeout-Apache-2.0.txt` | [v5.0.1](https://github.com/aio-libs/async-timeout/tree/v5.0.1) |
| astral 3.2 | Simon Kennedy and contributors | `licenses/Astral-Apache-2.0.txt` | [3.2](https://github.com/sffjunkie/astral/tree/3.2) |

Paho's package metadata describes its license as `EPL-2.0 OR BSD-3-Clause`; its included notice names the Eclipse Distribution License 1.0 alternative. Both upstream license texts are included here.

## Host platform and development tools

Thank you to the Falcon Player developers and [FPP plugin template](https://github.com/FalconChristmas/fpp-plugin-Template) contributors for the plugin interfaces and lifecycle guidance. FPP uses several licenses; see `licenses/FPP-license-overview.txt` and the installed FPP `LICENSE.*` files. FPP's Bootstrap styles are supplied by the host, with credit to [Bootstrap authors](https://github.com/twbs/bootstrap) (MIT).

The adapter uses the installed [JsonCpp](https://github.com/open-source-parsers/jsoncpp) library (Baptiste Lepilleur and contributors, MIT/public-domain terms as described upstream). Runtime and installation also rely on [CPython](https://www.python.org/psf/license/), [pip](https://github.com/pypa/pip), [PHP](https://www.php.net/license/), [Apache HTTP Server](https://httpd.apache.org/), [systemd](https://systemd.io/), the Linux kernel, GNU C library, GNU libstdc++, and timezone data. Build/development tools include GNU GCC, Make, Binutils, Bash, Git, Node.js/npm and Microsoft Playwright. These are separately supplied platform or development tools, not vendored plugin libraries. Their versions depend on the FPP/development image; retain that image's package copyright records (normally `/usr/share/doc/<package>/copyright`) when redistributing an image.

## Provenance and remaining review

The component inventory covers this plugin's selected rendering source, browser assets and pinned Python dependencies; unused ESP dependencies and usermods in the WLED checkout are not included in the Linux runtime. License copies for Python packages come from the exact installed distributions; Paho's full alternative texts come from its v2.1.0 source. WLED and FPP revisions are recorded in `upstream.lock.json`.

Some inherited artwork needs further provenance work before a final binary release: WLED labels several bitmap fonts public domain, but its console font header only links to raster-fonts, whose repository does not supply a blanket license; WIcons does not include an explicit per-icon license manifest. Tom Thumb's author explicitly permits CC0 or CC-BY 3.0 in his 2015 update; we use the CC0 option (see https://robey.lag.net/2010/01/23/tiny-monospace-font.html). Credits are included without assigning unsupported license terms. Preserve the upstream source and notices; these unresolved items remain release review gates.

The FPP plugin page links to offline credits and full local license texts. Installation copies this notice, `LICENSE`, `licenses/`, the upstream lock and dependency pins into each staged runtime release, so upgrades and rollback retain their accompanying notices.

Embedded font source headers and their attribution comments are copied intact from the pinned WLED tree. No third-party trademark endorsement is implied. Include this file, `LICENSE`, `licenses/`, the complete corresponding upstream source and all dependency license metadata when distributing binary release bundles. Dependency redistribution review and final binary release packaging remain alpha release gates.

The Linux preparation step makes explicit adaptations to WLED: virtual bus initialization, filesystem-map/custom-palette/font substitutions, pointer-width-safe palette reads, Linux platform wrappers, extraction of existing math helpers, and two browser integration changes (WebSocket port preservation and removal of embedded update checking). Generated files retain upstream headers and are reproducible from the pinned source plus this repository; they are not checked in.
