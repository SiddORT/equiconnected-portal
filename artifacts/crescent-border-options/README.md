# EquiConnected crescent border exploration

## Design anchor

The existing crescent geometry stays untouched: the ivory filled cut remains the
hero’s visual transition, and the existing SVG path remains the border path.
These options change only how that path is visually weighted and animated. The
subscriber form, hero copy, slider controls, indicators, focus states, and
keyboard behavior remain exactly where they are.

All three concepts use the same accessibility rule: the border has a calm,
non-animated static treatment when `prefers-reduced-motion: reduce` is active.
The animation is decorative only and should never be the sole way to perceive
the edge.

---

## Option 01 — Quiet Meridian

### Thickness and shape treatment

Use a substantial but precise two-layer edge:

- Keep the existing shadow path as a very soft, deep teal under-edge at roughly
  3–4px.
- Increase the gold path to roughly 2.5–3px, with a clean round cap and join.
- Let the shadow sit just below the gold line rather than expanding the ivory
  fill. The crescent therefore reads thicker without changing its geometry or
  consuming more space above the cut.

The visual result is a confident hairline-to-ribbon transition: clearly visible
on bright horse imagery, but still quiet enough for a healthcare portal.

### Gradient colors

The line moves between antique brass, pale oat gold, and muted champagne. Avoid
bright yellow; each stop should feel mineral and slightly desaturated.

### Animation behavior and timing

Animate the gradient position slowly from left to right and back again over
about 8 seconds, using a soft ease-in-out. The line should feel as though warm
light is passing across the arch, not as though it is glowing.

In the reduced-motion fallback, freeze the gradient at the middle position and
use the same 2.5–3px brass treatment. No opacity pulsing, shimmer, or movement.

### Intended emotional effect

Steady, reassuring, and quietly premium. It reinforces the idea that care is
continuous and considered, while keeping the hero image and message in front.

### Main trade-off

This is the safest and most restrained option, so it has the least dramatic
before-and-after impact. On very busy or dark images, the line may still feel
more refined than emphatic.

---

## Option 02 — Tidal Brass

### Thickness and shape treatment

Create a more tactile border by widening the gold path to roughly 4–5px and
using the existing shadow as a narrow offset seam beneath it:

- Gold edge: broad, softly rounded, visually similar to a satin ribbon.
- Shadow seam: a restrained deep blue-green line offset by approximately 1px.
- Keep the ivory fill edge crisp and uninterrupted; the added weight belongs to
  the border, not the cut.

On small screens, visually cap the border closer to 3–3.5px so it does not
compete with the compact controls or make the crescent feel heavy.

### Gradient colors

Use a coastal, equine-adjacent sequence: weathered brass, soft clay rose, and
quiet sea-glass teal. The teal should be a muted blue-green rather than a
literal bright accent. The gradient gives the edge a sense of connected
systems—earth, body, and water—without becoming ornamental.

### Animation behavior and timing

Run a single directional sweep along the arch over 10–12 seconds. The color
field should travel slowly from one end to the other, then settle briefly for
roughly 2 seconds before restarting. Use a long ease-in-out and no flashing.

For reduced motion, remove the sweep and keep a static brass-to-sea-glass
gradient with the same 4–5px visual weight. The static gradient preserves the
identity even when motion is disabled.

### Intended emotional effect

Connected, alive, and human. It introduces a gentle sense of flow that supports
EquiConnected’s promise of bringing owners, providers, and care details into
one calm continuum.

### Main trade-off

The wider ribbon and three-color sweep are more noticeable. If the image
composition is already visually dense, this can pull attention toward the
bottom edge and slightly reduce the gallery’s quietness.

---

## Option 03 — Gilded Horizon

### Thickness and shape treatment

Use a layered “lit horizon” treatment that feels premium without changing the
curve:

- Primary arch: approximately 2px, with a warm metallic gradient.
- Secondary highlight: a very narrow, low-opacity line aligned to the upper
  half of the primary stroke.
- Existing deep teal shadow: retain it at a restrained 2–3px so the crescent
  stays legible against pale and dark slides.

The perceived thickness comes from the stacked tonal bands rather than a
single heavy stroke. Keep the highlight inside the border footprint so it
cannot cover the subscriber form or slider controls.

### Gradient colors

Use ivory champagne at the center, antique gold near the shoulders, and a
slightly smoky bronze at the outer ends. The center should be the lightest
point, echoing a horizon catching first light.

### Animation behavior and timing

Apply an extremely slow “breathing horizon”: the brightest point drifts from
center-left to center-right over 14 seconds, then returns over 14 seconds. Keep
the color shift subtle; do not animate stroke width or opacity. The motion
should be nearly imperceptible during normal reading.

For reduced motion, lock the highlight at center and retain a static
champagne-to-bronze gradient. No transition is necessary when the preference
changes.

### Intended emotional effect

Trustworthy, ceremonial, and premium. It gives the hero a finished signature
that feels closer to a carefully engraved mark than a decorative UI effect.

### Main trade-off

The layered highlight needs the most visual tuning across image brightness and
responsive sizes. If the highlight is too strong, the edge can read as jewelry
or luxury branding rather than healthcare.

---

## Recommendation — Quiet Meridian

Choose **Quiet Meridian** for the EquiConnected homepage.

It best balances the product’s four identity signals: trusted, calm, connected,
and premium. The thicker gold edge will be immediately legible as an intentional
finish, while the muted brass movement adds life without competing with the
horse imagery, slide controls, indicators, or subscriber form. Its static
reduced-motion state is also the clearest: one dependable shadow seam and one
dependable brass line, with no loss of hierarchy.

For implementation, preserve the current SVG `d` values and layering order.
Treat the animation as a decorative gradient-position change on the existing
arch line only; do not animate the crescent fill, path geometry, control
positions, indicator positions, or any interactive element.