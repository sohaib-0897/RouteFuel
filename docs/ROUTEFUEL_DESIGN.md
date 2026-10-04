# RouteFuel visual system

## Audit before redesign
Resumed `frontend-recovery` at `334627e`; inspected its complete changes against protected backend checkpoint `8bb8943`. The recovery already contained the paper/navy/orange direction, real Django API client, lazy ThreeGlobe and MapLibre layers, ordered markers, response validation, error/retry handling, Docker integration, 14 frontend tests and 119 backend tests. Preserved that working foundation.

Captured the recovery at 1440×900, 1920×1080 and 390×844 before editing. The large globe crowded the headline and search area; headline drift added no meaning; endpoint inputs had no search; accuracy text was too small; Route Ready appeared before the map finished drawing. Refined these issues without replacing the application. Final captures and verification are in `FRONTEND_VERIFICATION.md`.

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
One-pixel rules; no glass surfaces, glowing borders, decorative gradients or repeated card surfaces. Search uses a small practical popup shadow to separate selectable results from the globe.
52px primary controls; minimum 44px touch targets where practical.
160ms hover, 240ms component, 650ms map camera; cubic-bezier(.2,.7,.2,1). A single geographic reveal gives the USA rotation and overview arc time to finish. Headline remains still; its position floats across the composition. Globe and map colors also read these tokens.
Orange indicates route/action; petrol indicates completion; no color-only state information.

## Composition
Editorial landing with an offset globe, large condensed type crossing the central space, and unboxed FROM/TO endpoint fields. The map occupies the majority of the results workspace. A ruled itinerary follows backend sequence alongside a sticky map. No fabricated route or station data.
Native scroll with an opt-in desktop ScrollTrigger walkthrough; no scroll hijacking or Lenis dependency.
Motion handles component state. GSAP handles the scene and optional walkthrough. CSS handles hover and loader mechanics. Each property has one owner.
All static content remains visible without entrance animation. Reduced motion disables animated line drawing, camera travel and walkthrough motion.

## Location search
FROM and TO are accessible comboboxes with a 275ms debounce, canceled stale requests, ArrowUp/ArrowDown, Enter, Escape, clear, highlighted results and pointer selection. Place names lead each result, with city/state or address context underneath. A fixed popup opens above the field when needed, adapts to the mobile visual viewport and scrolls the active result into view. Restored values do not automatically reopen a popup on focus.

`routes/locations.py` supplies the additive `GET /api/v1/locations/?q=…` endpoint, using the existing server-side routing HTTP boundary and key. It filters Pelias locality/venue/address results to the United States, validates points, deduplicates equivalent display rows and returns at most six results. Searches use an independent one-hour cache and the existing anonymous throttle; they never seed or change route geocoding caches. The selected `query` goes to the unchanged route POST. Full manual queries remain available if search is unavailable.

## Geographic honesty
Aceternity's ThreeGlobe geographic asset supplies the overview only. Its endpoint arc is labeled cinematic.
MapLibre renders the exact Django GeoJSON. Fuel prices, purchases, stops, distances and metadata are displayed from the response. Centroid stops are labeled approximate; their access values are uncertainty budgets.
