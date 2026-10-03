# Verification record

Executed on 2026-10-04 with Python 3.12.9 and Django 6.1.1. These are observed checks, not projected results.

## Automated and deployment checks

- Django system checks: no issues.
- OpenAPI generation with `spectacular --validate`: passed.
- `render.yaml` validated against Render's official JSON schema; `pip check` found no dependency conflicts.
- Ruff lint and formatting: passed.
- Normal tests mock third parties; no live key required. Full suite: **85 passed**, no skips. Includes dataset integrity, optimizer feasibility and conservation, independent purchase enumeration, API/cache/error tests, preprocessing, and map escaping.
- Docker image built successfully on Docker Desktop's Linux engine. Gunicorn served health, route, map, schema, and Swagger with `DEBUG=false`, running as an unprivileged user.
- `check --deploy` inside Docker with production HTTPS settings: no warnings or errors. HTTPS redirection is disabled only for local HTTP smoke tests.
- Chromium map verification: HTTP 200, five markers (two endpoints, three numbered stops), full route polyline, usable purchase popup, zero JavaScript errors. Screenshot is in ignored `artifacts/route-map.png`.
- Offline preprocessing rerun completed with the same counts and original checksum. The original input has no modifications; generated coordinates carry source quality.

## Real provider requests

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
