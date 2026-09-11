# Palette display follow-up — 2026-09-10

Palette selection reaches the runtime without replacing the effect's individual
color slots. For example, Android can use the primary color for its moving head
and the palette for its background. The color wheel therefore remains on the
selected color slot.

The main WLED color page now shows the selected palette's name and gradient above
the wheel, with a short explanation. Settings shows palette gradients alongside
the existing palette names, separately from configured color controls and sampled
live output. Dynamic color-slot palettes resolve against each segment's colors.
Open WLED pages refresh custom previews when the runtime palette revision changes.

`tests/browser_palette_overview.js` exercises real palette-list clicks with both
WLED and Settings open, external state changes, unchanged effect color slots,
dynamic palettes, and saving/updating custom palettes without reloading. Desktop
and mobile light/dark screenshots are generated in the ignored build directory.
`tests/browser_lighting_sync.js` covers settings readback and preserving drafts.

These checks use the synthetic FPP observer and local renderer, not physical LEDs.
