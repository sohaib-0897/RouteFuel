# Five-minute reviewer walkthrough

Prepare two editor tabs/groups, Postman, and a browser before recording. Start the app, import the collection, set `base_url`, and make sure the API key is configured without displaying `.env`. Keep the terminal command history and environment/key screens out of frame. Use a fresh map response because links expire.

## 0:00–0:30 — Assignment and architecture

Show the README diagram. Say: “This API accepts two U.S. locations, gets one complete driving route, and plans fuel purchases for a 500-mile, 10-MPG vehicle. The response includes GeoJSON and a browser map. The main performance decision is preparing station coordinates before traffic.”

## 0:30–1:15 — Dataset preprocessing

Show `data/preprocessing_stats.json`, then `routes/preprocessing.py`: `read_source`, `parse_census`, `load_centroids`, and `prepare`. Say: “The input has 8,151 rows. I filter 620 Canadian rows and remove 26 exact duplicates while preserving distinct records with repeated IDs. Census matches 588 addresses. Highway exits often do not match, so 6,440 use explicitly labeled city centroids; 477 are excluded. The generated file is committed. None of this happens inside a route request.”

## 1:15–2:15 — Django and routing

Show `routes/views.py:RouteView.post`, `routes/serializers.py:RouteRequestSerializer`, then `routes/service.py:plan_route` and `routes/routing.py:RoutingClient`. Say: “Validation rejects blank or non-string inputs and equivalent endpoints. Geocoding verifies U.S. country and confidence. The current HeiGIT service paths make two geocodes and one directions call on a cold request. I cache locations, directions, and plans; timeout and malformed-response errors have explicit statuses. API keys stay server-side.”

## 2:15–3:00 — Fuel optimization

Show `routes/stations.py:StationIndex.candidates`, then `routes/optimization.py:leg_distance`, `optimize`, and `purchase_on_path`. Say: “Candidates follow actual route geometry. I estimate access distance and budget extra uncertainty for centroid records. DAG edges obey the 500-mile limit including access. Path selection uses prices; greedy purchasing then carries cheaper fuel along that itinerary. Initial fuel is charged at a disclosed local reference price, so it is never free. I claim fixed-itinerary purchase optimality, not globally optimal routing.”

## 3:00–4:15 — Postman and map

Send the collection's health request, then Dallas → Los Angeles. Show the response's route distance, vehicle, initial fueling, numbered stops, gallons, total cost, longest leg, and quality warnings. Open `base_url + map_url` and click a fuel marker. Say: “The main geometry is complete. Each popup shows name, price, purchase, cost, and whether the coordinates are approximate. Detours are estimates rather than extra directions calls.” Send the same request again and point to Postman's observed elapsed time; do not promise a fixed benchmark. If upstream availability prevents a live response, state the actual error and show the saved successful sample, identifying it as recorded output.

## 4:15–4:40 — Tests and call count

Show `pytest -q` results and `tests/test_api.py:test_integration_three_calls_cached_repeat_and_map`. Briefly show `tests/test_optimization.py:test_fixed_path_greedy_against_exhaustive_integer_fuel`. Say: “Tests mock external services, assert three cold calls and zero repeat calls, check exact range boundaries and fuel conservation, and independently enumerate purchase choices to check the greedy rule.”

## 4:40–5:00 — Deployment and close

Show `render.yaml`, `Dockerfile`, and the README tradeoffs. Say: “The deployment uses Gunicorn and committed station data; it never geocodes on boot. Render needs the repo connection and secrets. The main limitation is station-location and access uncertainty, which the API exposes. The README contains setup, Postman, tests, and reproducible preprocessing.” Close on `docs/SUBMISSION.md` with the final links filled in.
