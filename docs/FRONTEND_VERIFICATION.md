# RouteFuel recovery verification — 2026-10-04

Resumed `frontend-recovery` from `334627e`, after inspecting the frontend and `git diff 8bb8943..334627e`. No reset or replacement checkout was used. The existing route service, routing client, optimizer, station index, datasets and protected tests remain unchanged against `8bb8943`. The only backend addition is the independent place-search module and its URL/tests, committed as `e221527`.

## Visual review

Rendered and inspected the recovery before editing at 1440×900, 1920×1080 and 390×844. Kept the editorial atlas composition already in the recovery: offset Aceternity globe, asymmetric condensed typography, unboxed endpoint controls and a ruled itinerary. Reduced globe crowding, removed continuous headline drift and solid input patches, made coordinate-accuracy text readable at 12px, and enlarged map zoom targets to 44px.

Compared paper/navy/orange, stone/charcoal/petrol, and gray/ink/yellow in browser captures under `artifacts/routefuel-audit/palette-*.png`. Selected **warm off-white `#f4f1e9`, navy `#172d3b`, route orange `#b74421`**, with `#d04b24` for the road line. Orange gives the clearest separation between route geometry, geographic background and interface. Shared tokens also supply globe and map colors.

Reviewed final landing, route, dropdown, loading/error, station detail, overview switch, reduced-motion and long-name screenshots. Desktop was inspected at 1440×900 and 1920×1080; mobile at 390×844; an additional 820×1180 tablet sweep passed. No horizontal overflow at these sizes. A restored endpoint previously reopened its dropdown and intercepted the next Plan Route click; it now stays closed until edited or opened with an arrow key. Fresh captures confirmed the complete mobile road map and markers after resizing.

| View | Landing | Real Docker route |
|---|---|---|
| 1440×900 | [Desktop](screenshots/routefuel-desktop.png) | [Dallas → LA](screenshots/routefuel-route-desktop.png) |
| 1920×1080 | [Wide](screenshots/routefuel-wide.png) | [Dallas → LA wide](screenshots/routefuel-route-wide.png) |
| 390×844 | [Mobile](screenshots/routefuel-mobile.png) | [Dallas → LA mobile](screenshots/routefuel-route-mobile.png) |

[Mobile autocomplete and active result](screenshots/routefuel-search-mobile.png). Selected captures are committed under `docs/screenshots/`; complete browser screenshots/traces/reports remain in ignored `artifacts/` and `frontend/playwright-report/`.

## Search and real route flow

FROM/TO search uses a 275ms debounce, cancellation and late-response checks, two-line name/context results, keyboard navigation, Enter selection, Escape, clear, pointer selection, retry and accessible combobox/listbox semantics. The popup adjusts to available viewport space and the mobile visual viewport; keyboard selection scrolls its active row into view. There is no embedded city list or provider key in React.

`GET /api/v1/locations/?q=…` accepts 2–120 characters, requests up to eight [Pelias autocomplete](https://github.com/pelias/documentation/blob/master/autocomplete.md) locality/venue/address candidates, independently validates U.S. country and point geometry, removes equivalent display rows and returns at most six. It uses the existing server-side authorization/error boundary, a separate one-hour cache, and the existing 60/min anonymous throttle. It does not seed or mutate route geocoding caches. Its selected query is sent to the existing route POST; manual full-location submission remains available when search fails.

The normal flow retains Newton's cradle, globe rotation toward the USA, the visual overview arc, GSAP transition, the exact backend GeoJSON road draw, ordered actual stops and route statistics. ROUTE READY appears only after the map draw completes. Centroid stops remain visibly approximate; centroid access remains an uncertainty budget. Origin fuel remains a price reference rather than a fabricated stop. Motion, GSAP/ScrollTrigger and the liquid Globe/Map switch remain; native scrolling is retained.

## Completed checks

| Check | Result |
|---|---|
| `npm run typecheck` | Passed |
| `npm run lint` | Passed |
| `npm test` | 19 passed across two files |
| `npm run build` | Passed on Windows and inside Linux Docker |
| `npx playwright test` | Four passed; real WebGL, keyboard/pointer, retry, reduced motion, long names, responsive layouts |
| Axe browser scans | Zero violations in tested hero, dropdown and route states, including mobile |
| Browser runtime | No page/console errors; one active rendering canvas |
| Full `pytest` suite | 131 passed, no skips; all protected backend tests preserved |
| Ruff lint/format | Passed |
| Django system check / OpenAPI validation | Passed |
| Docker HTTP smoke | UI root, health, Swagger, schema, route, returned Leaflet map and invalid request passed |
| Live Docker browser smoke | Actual autocomplete selections and route POST for Dallas → LA and Dallas → Austin passed |
| `git diff --check` | Passed |
| Original CSV SHA-256 | Unchanged: `c704371f141ded9c54df6c32d488a0ba2ceb589f88c936c967daa5330e0cd241` |

Frontend tests use Vitest (`src/test/*.test.tsx`); browser tests use Playwright (`e2e/*.spec.ts`). Backend tests use the existing pytest framework (`tests/test_*.py`); the added cases cover search input, malformed data, U.S. filtering, deduplication, bounds, cache separation, authorization and safe error responses. Browser tests inject the recorded response for deterministic interaction tests; the separate production smoke makes real unmocked requests.

## Protected route comparison

Captured the existing protected backend before editing and compared it against saved `artifacts/routefuel-baseline/` responses. Then compared the fresh Docker server field-by-field. Geometry, stops, purchases, fuel, vehicle assumptions, optimization and warnings all match exactly; the regression capture additionally compares resolved endpoints. Expiring map URLs are deliberately excluded.

| Route | Road miles | Fuel cost | Additional stops |
|---|---:|---:|---:|
| Dallas → Los Angeles | 1442.68 | $426.77 | 3 |
| Dallas → Austin | 200.46 | $57.78 | 0 |

Dallas → LA retains 1475.48 modeled miles including access, 147.5483 gallons, a 474.2284-mile longest modeled leg and zero modeled arrival fuel. Final Docker HTTP smoke took 4.8052 seconds first / 0.0427 seconds cached for that route. The live browser POST samples were 0.758 seconds for Dallas → LA and 2.286 seconds for Dallas → Austin; these are local samples, not throughput guarantees. Browser bootstrap recorded CLS 0 and LCP 408ms; software WebGL still produced a 745ms maximum long task. Large globe/map bundle warnings remain; modules remain lazy and are disposed when hidden.

## Reproduce

From the repository root:

```powershell
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --tb=short
.venv/Scripts/ruff.exe check .
.venv/Scripts/ruff.exe format --check .
.venv/Scripts/python.exe manage.py check
.venv/Scripts/python.exe manage.py spectacular --validate --file artifacts/routefuel-schema.yaml
git diff --check
docker build -t routefuel-resume:final .
docker run -d --name routefuel-final-qa -p 127.0.0.1:8006:8000 --env-file .env -e DJANGO_DEBUG=false -e DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1 routefuel-resume:final
.venv/Scripts/python.exe scripts/smoke_test.py --base-url http://127.0.0.1:8006
.venv/Scripts/python.exe scripts/routefuel_regression.py --base-url http://127.0.0.1:8006 --output artifacts/routefuel-final --compare artifacts/routefuel-resume-baseline
```

The final container is currently running at **http://127.0.0.1:8006/**. Reuse it for smoke tests; do not rerun its `docker run` command with the same name while it exists. Baseline JSON files are local ignored artifacts.

From `frontend/`:

```powershell
npm run typecheck
npm run lint
npm test
npm run build
npx playwright test
node scripts/production-smoke.mjs http://127.0.0.1:8006
```

For palette/visual audit captures, run Vite on 5187 and a current Django server separately, then `node scripts/capture-audit.mjs http://127.0.0.1:8004` (substitute the current Django port). This tool forwards place search to that server and uses the clearly recorded route fixture for its map capture. Production screenshots above use the actual Docker response.

## Remaining manual work

Implementation and requested local QA are complete. Publishing the repository, deploying the current image/Render service with server-side secrets, recording the Loom walkthrough and filling the URLs in `SUBMISSION.md` remain manual submission steps. Deployment must include the additive search endpoint; an older backend-only container cannot serve autocomplete. No external publication or messages were sent.
