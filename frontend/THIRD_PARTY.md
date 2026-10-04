# Geographic and interface sources

- Globe: adapted from [Aceternity GitHub Globe](https://ui.aceternity.com/components/github-globe), by Manu Arora. The registry CLI was verified and attempted. Its alpha React Three dependency conflicted with the stable renderer; the adaptation retains ThreeGlobe's hex polygons, geographic asset, endpoint rings and arc layer and uses a managed Three.js scene. [Aceternity terms](https://ui.aceternity.com/licence).
- Globe polygons: the documented [globe.json asset](https://assets.aceternity.com/globe.json), frozen in public/globe.json. It supplies a visual overview, never driving geometry.
- Three.js and three-globe: MIT; licenses in their packages.
- MapLibre GL JS: BSD-3-Clause. Uses the keyless [OpenFreeMap public instance](https://openfreemap.org/quick_start/) with the Positron style. Its built-in OpenFreeMap, OpenMapTiles and OpenStreetMap attributions remain visible. [OpenStreetMap copyright and ODbL](https://www.openstreetmap.org/copyright). The public tile service is an external availability dependency; a Leaflet fallback link remains available.
- Barlow Condensed and IBM Plex Sans: self-hosted Latin font files from Fontsource, SIL Open Font License 1.1. License files are included in the installed font packages.
- The shine, circular completion check, liquid switch and Newton cradle are original implementations of the requested Uiverse visual concepts. No original snippets or author URLs were supplied. They share RouteFuel tokens and accessible semantics; they are not copied third-party source.
- GSAP and ScrollTrigger: [standard license](https://gsap.com/community/standard-license/); Motion: MIT. Runtime dependencies retain their upstream licenses.
