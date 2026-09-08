# Discovery and synchronization

Open **WLED Settings → Discovery & synchronization**, or the WLED **Sync** button.
Save runtime access first. Network settings apply immediately without restarting FPP or the renderer.

1. Enable **Discover WLED instances** and **Make this instance discoverable**. Set a recognizable name and the FPP web port (normally 80).
2. Enable **UDP synchronization**, **Automatically sync with discovered instances**, and the desired Send/Receive directions.
3. Select matching groups on each WLED instance; group 1 and UDP 21324 are conventional defaults. Enable the appropriate sending and receiving options on each native device too.
4. Save. Allow up to a minute for discovery. Instances appear in Settings and Nodes; peer addresses, packet counters and errors appear below the controls.

Discovery alone does not change lighting. New and existing installations retain their network settings until enabled here. You may add explicit IPv4 peers for networks where discovery broadcasts do not cross routers. Automatic peers exclude every manually enrolled device, avoiding conflicting effect/sync/FPP-stream modes. Unsupported effects report an error instead of silently substituting another effect.

## Interoperability

- Listens for and advertises WLED's 44-byte node packets on UDP 65506.
- Browses/advertises `_wled._tcp.local.` over mDNS (UDP 5353), including FPP's web port and `/fpp-wled/` TXT path.
- Exchanges WLED v12 notifier packets on the chosen sync port. Supported brightness, colors, effects, palettes and segment options synchronize; geometry remains local. Matching local segment IDs receive updates, and the sender's effect clock is adopted. Random effects, different layouts and unsupported features are not guaranteed identical pixels. Preset IDs/files are not distributed by UDP: synchronize the recalled lighting state, or use enrolled effect-mode preset commands.
- Send/receive use a shared group mask. The UI exposes the eight groups. Packets from undiscovered/unlisted addresses are ignored; discovery is not authentication and is intended for a trusted lighting LAN.
- Native WLED's Nodes wire format carries no HTTP port or path. Its link to this runtime opens the FPP origin, not `/fpp-wled/`. The plugin's own Nodes/Settings links honor mDNS port/path information. Stock FPP's root and native WLED endpoints are not replaced.
- Discovery expires absent UDP nodes after three minutes; mDNS entries follow service removal. Networks must permit local multicast/broadcast; discovery does not cross VLANs automatically.

## Shows and failure behavior

This runtime sends no ambient sync during show ownership or disabled ambient and discards incoming sync during that period. Received packets never echo back. It announces discovery while shows run, since those packets do not command lighting. On ambient recovery it sends the restored selection. Native WLED itself ignores notifier packets while realtime owns its output; this plugin never sends a realtime override. Direct-to-device shows still require explicit Show Start/End hooks for guaranteed coordinated handoff.

Listener failures are reported in `/api/network` and Settings instead of crashing the renderer. Correct the conflict and save again. A discovery failure leaves automatic peers empty; explicit peers remain available if the sync listener starts.

## API and verification

GET `/api/network` reports saved active runtime settings, listener state, resolved peers, counters and errors. Authenticated POST `/api/network` accepts `name`, `discovery`, `discoverable`, `discovery_http_port` and `udp`; it validates and persists them, then replaces network listeners. GET `/api/discovery` lists candidates and GET `/json/nodes` supplies the WLED Nodes list.

Tests cover the pinned native discovery packet format, mDNS advertisement metadata, node removal/expiry, port conflicts, configuration persistence, actual UDP send/receive, group rejection, show suppression, no echo loops and managed-device exclusion. Chromium checks cover saving live settings and a 320px viewport. Physical native-WLED interoperability remains a hardware acceptance item.

Protocol references: pinned WLED `wled00/udp.cpp` and [WLED UDP notifier documentation](https://kno.wled.ge/interfaces/udp-notifier/).
