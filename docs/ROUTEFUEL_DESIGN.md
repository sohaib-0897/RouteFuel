# RouteFuel visual system

## Audit before redesign
The existing implementation already had a real Django API client, lazy ThreeGlobe and MapLibre layers, ordered markers, response validation, error/retry handling, accessibility controls, Docker integration, 14 frontend tests and 119 backend tests. Keep that foundation.

Replace the centered lime-on-black hero, floating boxed form, tiny low-contrast map labels, logo decoration, large footer, repeated metric dividers, and viewport-triggered itinerary fades. These choices made the experience feel generic and hid content in full-page captures.

## Direction considered
- Warm off-white / navy / route orange: selected. Paper-map familiarity, strong reading contrast, and an orange route distinguish geographic data from the interface.
- Sand / charcoal / petrol green: calm, but too close to the initial olive treatment and less distinct against map vegetation.
- Neutral gray / ink blue / safety yellow: clear for dispatch, but yellow is weaker on a light basemap and reads as warning.

## Tokens
Source of truth: frontend/src/tokens.css.
Paper #f4f1e9; surface #fbfaf6; navy #172d3b; muted #58666c; orange #b74421; route line #d04b24; petrol success #33574d.
Barlow Condensed 500/600 for display and station names; IBM Plex Sans 400/500/600 for controls/body; system monospace for compact geographic labels. Fonts are self-hosted with SIL OFL licenses.
4px spacing base: 4, 8, 12, 16, 24, 32, 48.
2px corner radius. Circles are reserved for geographic endpoints, station numbers, completion, and the requested liquid switch.
One-pixel rules; no glass surfaces, glowing borders, decorative gradients or card shadows.
52px primary controls; minimum 44px touch targets where practical.
160ms hover, 240ms component, 650ms camera; cubic-bezier(.2,.7,.2,1). A single restrained geographic reveal. Hero drift limited to 3px over 10s.
Orange indicates route/action; petrol indicates completion; no color-only state information.

## Composition
Editorial landing with an offset globe, large condensed type crossing the central space, and unboxed FROM/TO endpoint fields. The map occupies the majority of the results workspace. A ruled itinerary follows backend sequence alongside a sticky map. No fabricated route or station data.
Native scroll with an opt-in desktop ScrollTrigger walkthrough; no scroll hijacking or Lenis dependency.
Motion handles component state. GSAP handles the scene and optional walkthrough. CSS handles hover and loader mechanics. Each property has one owner.
All static content remains visible without entrance animation. Reduced motion disables float, animated line drawing, camera travel and walkthrough motion.

## Geographic honesty
Aceternity's ThreeGlobe geographic asset supplies the overview only. Its endpoint arc is labeled cinematic.
MapLibre renders the exact Django GeoJSON. Fuel prices, purchases, stops, distances and metadata are displayed from the response. Centroid stops are labeled approximate; their access values are uncertainty budgets.
