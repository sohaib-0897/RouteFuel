# Verification record

Executed on 2026-10-04 with Python 3.12.9 and Django 6.1.1. These are observed checks, not projected results.

## Automated and deployment checks

- Django system checks: no issues.
- OpenAPI generation with `spectacular --validate`: passed.
- `render.yaml` validated against Render's official JSON schema; `pip check` found no dependency conflicts.
- Ruff lint and formatting: passed.
- Normal tests mock third parties; no live key required. Full suite after accuracy hardening: **117 passed**, no skips, preserving the original 85 tests. Includes dataset integrity, optimizer feasibility and conservation, independent purchase enumeration, API/cache/error tests, preprocessing, map escaping, and coordinate-quality decisions.
- Docker image built successfully on Docker Desktop's Linux engine. Gunicorn served health, route, map, schema, and Swagger with `DEBUG=false`, running as an unprivileged user.
- `check --deploy` inside Docker with production HTTPS settings: no warnings or errors. HTTPS redirection is disabled only for local HTTP smoke tests.
- Chromium map verification: HTTP 200, five markers (two endpoints, three numbered stops), full route polyline, usable purchase popup, zero JavaScript errors. Screenshot is in ignored `artifacts/route-map.png`.
- Offline preprocessing rerun completed with the same counts and original checksum. The original input has no modifications; generated coordinates carry source quality.

## Initial implementation: real provider requests

| Route | Main miles | Stops | Estimated total fuel | Longest modeled leg | Observed first/repeat latency |
|---|---:|---:|---:|---:|---:|
| Dallas → Los Angeles (final Docker/Gunicorn image) | 1,442.68 | 3 | $424.94 | 474.2284 mi | 3.4305 / 0.0347 s |
| Dallas → Austin (Windows development server) | 200.46 | 0 | $57.78 | 200.4596 mi | 3.1205 / 0.4632 s |
| 350 5th Ave, New York → Seattle (Windows development server) | 2,868.25 | 8 | $932.79 | 485.6437 mi | 30.2111 / 2.1555 s |

The Docker Dallas route consumed an estimated 148.6547 gallons over 1,486.55 modeled miles including station access. Initial fuel is included in cost. Tests explicitly assert two geocodes and one directions request on a cold successful API call, and zero external calls on the cached repeat. Actual timings include provider/network variability and are single samples, not benchmark distributions.

## Review findings and resolved issues

- DRF attempted to import Django auth models despite anonymous access: configured `UNAUTHENTICATED_USER=None`.
- CSV cache newline conversion on Windows could introduce blank rows: preserve Census newlines and safely ignore blank lines while enforcing complete response IDs.
- DRF's default text field accepted numeric values: location fields now require actual strings.
- Added checks for non-object upstream JSON, invalid country metadata, low-confidence matches, nonfinite summary numbers, geometry/summary distance consistency, endpoint snapping, and route/data absence.
- Added CSRF and frame-protection middleware; verified production HTTPS/HSTS checks.
- Removed zero-purchase visits and their access mileage before recomputing fuel purchases.
- Confirmed longitude/latitude order, miles/meters conversion, U.S. state filtering, original CSV hash, unrounded fuel conservation, and secret exclusion.

Remaining model limitations are disclosed in the README and API: centroid positions and access roads are estimates; no global itinerary optimality or real-world access/range guarantee is asserted. Render deployment, GitHub publishing, and recording Loom require the account steps in `docs/SUBMISSION.md`.

## Geospatial accuracy hardening

### Address audit and Census acceptance

The supplied descriptions mostly lack conventional postal street numbers. Categories are exclusive, with exit descriptions taking precedence over intersections; examples and Census outcomes are committed in `data/address_audit_before.json` and `data/address_audit_after.json`.

| Address pattern | All 8,151 source rows | Unique U.S. records |
|---|---:|---:|
| Conventional numbered street | 7 | 7 |
| Highway/interstate without junction or exit | 1,670 | 1,415 |
| Exit description | 4,616 | 4,397 |
| Intersection | 1,826 | 1,681 |
| Malformed/partial | 4 | 1 |
| Other recognizable descriptions | 28 | 4 |

The four other U.S. descriptions are `BUS-71`, `US-BUS 53`, `Country Road 527`, and `LINCOLN HWY`. The partial description is just a comma. This is distinct from malformed CSV fields: the original field/price validation count remains zero. Five of seven conventional descriptions matched Census; two did not. Bare highways and exit descriptions generally lack the address structure expected by the [Census geocoder](https://geocoding.geo.census.gov/geocoder/Geocoding_Services_API.html).

Before normalization, Census returned 588 `Match`, 6,637 `No_Match`, and 280 `Tie` statuses. Inspection found unsafe interpretations: exit 219 became street number 219, I-15 became 15th Avenue, and a same-state match could be in another city. Only **144 of the original 588** pass the new conservative checks.

Normalization standardizes whitespace, punctuation and road abbreviations, preserves highway numbers/classes, and removes an exit number only when named crossing roads identify a junction. It changes 7,413 queries, retains original descriptions, and invents no street numbers or ZIP codes. A normalized batch was justified by these junction patterns. An initial 502 left existing output intact; a later complete batch succeeded. It returned 963 matches, 5,965 nonmatches and 577 ties. Rejecting 310 invented-house-number, 432 different-city and 67 changed-road-identifier matches leaves **154 accepted Census locations**, ten more than the validated original batch. Strict city matching can reject postal aliases; those records remain eligible for the fallback.

Final coverage: **154 Census (2.20% of located), 6,859 centroids (97.80%), 492 excluded; 7,013 located out of 7,505 unique U.S. records (93.44%)**. The apparent reduction from 588 Census locations removes false precision rather than hiding failures. GeoNames input remains unchanged. Offline preparation reproduces these counts and the generated files. Original CSV SHA-256 remains `c704371f141ded9c54df6c32d488a0ba2ceb589f88c936c967daa5330e0cd241`.

### Planning and API changes

Census candidates retain the 15-mile corridor and 20-mile round-trip access cap. City candidates use a configurable 35-mile corridor so a displaced city centroid does not eliminate highway coverage. Their one-way planning budget is `1.4 × centroid-to-route miles + 5`, capped at 110 round-trip miles. A centroid directly on the route still has a ten-mile round-trip allowance. These budgets are conservative heuristics, not verified access roads or statistical error bounds.

The DAG score adds a configurable $15 per centroid stop to favor reasonably competitive Census alternatives. This selection penalty is excluded from fuel purchases and total fuel cost. Centroids remain available when needed for feasibility. Initial price-reference selection also favors nearby Census coordinates using a five-mile centroid distance penalty. All modeled legs, including access budgets, remain at most 500 miles; actual road-access feasibility cannot be guaranteed from centroid data.

Existing API fields remain, with additive `location_is_approximate`, `detour_is_estimated`, `detour_basis`, and centroid offset metadata. Census access is also estimated because no station-access routing call is made; it is correctly labeled as geodesic access rather than a centroid uncertainty budget. Plans use a new policy version and include all quality settings in their cache keys. Geocode/directions caches, TTLs and three-call cold-request behavior are unchanged. Tests prove policy changes recompute plans without repeating upstream calls. No routing-client or frontend changes were made.

### Before/after real route comparison

Both runs used Docker/Gunicorn on localhost:8001, a fresh application cache at the start of each run, and the same request order. Dallas–Austin can reuse the preceding Dallas geocode. New York uses `350 5th Ave, New York, NY`. Provider route geometry and distance were **identical before/after for all three routes**. All six map responses were HTTP 200.

| Route | Fuel cost before → after | Stops before → after | Census/centroid stops after | Longest modeled leg before → after |
|---|---:|---:|---:|---:|
| Dallas → Los Angeles | $424.94 → $426.77 | 3 → 3 | 1 / 2 | 474.2284 → 474.2284 mi |
| Dallas → Austin | $57.78 → $57.78 | 0 → 0 | 0 / 0 | 200.4596 → 200.4596 mi |
| New York → Seattle | $932.79 → $963.46 | 8 → 7 | 4 / 3 | 485.6437 → 445.8250 mi |

Dallas–Los Angeles modeled miles/gallons changed from 1,486.55 / 148.6547 to 1,475.48 / 147.5483. New York–Seattle changed from 2,944.70 / 294.4702 to 2,916.58 / 291.6577. Dallas–Austin remained 200.46 miles / 20.046 gallons. Costs include origin fuel and all purchases, without the selection penalty. Higher estimated costs reflect quality-aware station choices, not an effort to minimize these particular examples.

| Route | Before first / repeat | After first / repeat |
|---|---:|---:|
| Dallas → Los Angeles | 4.2616 / 0.0355 s | 4.0275 / 0.0395 s |
| Dallas → Austin | 1.2728 / 0.0142 s | 1.0258 / 0.0517 s |
| New York → Seattle | 6.5807 / 0.0906 s | 6.8221 / 0.1631 s |

These are single measured HTTP samples including network and serialization, not benchmark distributions. Full local responses are retained in ignored `artifacts/geospatial/`.

### Hardening verification

- Windows: `pytest -q -p no:cacheprovider --tb=short`: 117 passed. Linux Docker: 117 passed. No original tests removed or skipped.
- New cases cover preserved preprocessing quality, safe normalization, rejected false matches, competitive accurate alternatives, cheap centroid fake-zero access, required centroid coverage, wider city tolerance, labeled uncertainty, range conservation and quality-policy cache invalidation.
- `ruff check .`, `ruff format --check .`, Django system checks, validated OpenAPI generation and Docker production `check --deploy`: passed.
- Docker image build and health/route/map/schema/Swagger smoke test: passed with `DEBUG=false`. Production boot uses committed data without geocoding.
- Offline preprocessing, original-source checksum, secret exclusion, unchanged routing-client diff and `git diff --check`: verified.
