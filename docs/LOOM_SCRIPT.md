# RouteFuel reviewer walkthrough — 4 minutes 55 seconds

Prepare the RouteFuel page, Swagger or Postman, two editor groups, the verification report and README. Start Docker, configure the real key server-side, and keep .env and key screens out of frame. Use a fresh route result because fallback map URLs expire. Show actual outputs and measured timings; identify recorded output explicitly if upstream service is unavailable.

## 0:00–0:20 — Product and boundary
Show the RouteFuel landing page. “This is a Django backend assessment with a small React route-planning interface. Django computes every route, fuel stop and purchase. The globe is a geographic overview.”

## 0:20–0:50 — One route
Enter Dallas, TX → Los Angeles, CA. Let the globe become the road map. Point to the estimated fuel total and one approximate stop. “The road line is the returned GeoJSON. City-centroid stops are approximate areas; their access distances are planning budgets.” Keep animation coverage under 30 seconds.

## 0:50–1:25 — Standalone API
Open /api/docs/ or Postman and submit the same request. Show route.geometry, initial_fueling, fuel_stops, fuel and accuracy metadata. “The API remains independently usable. The frontend does not recalculate its values.” Show the existing Leaflet map URL briefly.

## 1:25–2:15 — Django and the three-call design
Show routes/views.py, routes/service.py and routes/routing.py. “A completely cold successful request uses two endpoint geocodes and one directions request. There are no runtime station-geocoding calls. Validation and upstream failures have explicit statuses. Locations, directions and plans are cached; a cached repeat needs no provider calls.”

## 2:15–3:10 — Preprocessing and spatial accuracy
Show preprocessing_stats.json, addresses.py and stations.py. “8,151 original rows become 7,505 unique U.S. records while preserving legitimate repeated IDs. There are 154 conservative Census matches, 6,859 city centroids and 492 exclusions. Generated data is committed; production startup never geocodes.” Show the two quality profiles and centroid metadata.

## 3:10–3:55 — Optimizer and fuel
Show leg_distance, optimize and purchase_on_path. “DAG edges obey a 500-mile modeled-leg limit including access. Itinerary selection is cost-aware and includes a centroid penalty that is never billed. Greedy purchasing carries cheaper fuel along the selected itinerary. Origin fuel is charged. This is not a claim of globally optimal routing.”

## 3:55–4:25 — Tests and performance
Show the latest verification report: original 117 tests retained plus integration tests, mocked frontend tests, browser checks and exact live regression comparison. Show the cold/repeat timings as individual samples. Point to the existing three-call/zero-call test and exhaustive fixed-itinerary purchase test.

## 4:25–4:50 — Deployment and documentation
Show Dockerfile, render.yaml and README. “One Docker deployment builds Vite in a Node stage, then serves Django and compiled assets through Gunicorn and WhiteNoise. The browser never receives the routing key.” Mention coordinate/access uncertainty and snapshot fuel prices.

## 4:50–4:55 — Close
Show the repository and submission links. “The README includes setup, API examples, assumptions, reproducible checks and deployment instructions.”
