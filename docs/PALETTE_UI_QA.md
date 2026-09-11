# Palette display follow-up — 2026-09-10

The main WLED palette picker now seeds the Fx/Bg/third color slots from the
selected palette's end, midpoint and start. The full palette remains active until
the user edits a color. Editing a slot switches to WLED's native Color Gradient
(palette 4), so palette-driven effects use the edited colors. Choosing another
fixed/custom palette reloads its representative colors. Color-derived palettes
already use the slots and retain them. Preset recall retains its saved colors.
This is a plugin UI convenience; native JSON API and preset semantics are unchanged.
It does not rewrite built-in palettes or overwrite saved presets/custom palettes.

The above-wheel palette preview was removed on 2026-09-11 following user feedback;
the palette list retains its native selection and previews. Settings shows palette gradients alongside
the existing palette names, separately from configured color controls and sampled
live output. Dynamic color-slot palettes resolve against each segment's colors.
Open WLED pages refresh custom previews when the runtime palette revision changes.

`tests/browser_palette_overview.js` exercises real palette-list clicks with both
WLED and Settings open, external state changes, refreshed effect color slots,
dynamic palettes, and saving/updating custom palettes without reloading. Desktop
and mobile light/dark screenshots are generated in the ignored build directory.
`tests/browser_lighting_sync.js` covers settings readback and preserving drafts.
`tests/browser_profile_colors.js` checks slot selection, editing, profile switching
and preset round trips. `tests/browser_theme_modes.js` checks dark by default,
explicit light/dark persistence and opt-in system following. A saved explicit
appearance choice still takes precedence over the new dark default.

These checks use the synthetic FPP observer and local renderer, not physical LEDs.
