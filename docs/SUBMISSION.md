# Spotter backend assessment submission

Hi Spotter team,

Here is my completed Django fuel-routing assessment:

- GitHub: `<GITHUB_URL>`
- Live API (Render): `<RENDER_URL>`
- Five-minute Loom walkthrough: `<LOOM_URL>`
- Swagger: `<RENDER_URL>/api/docs/`
- Health: `<RENDER_URL>/health/`

The API returns a full GeoJSON route, an estimated cost-aware fuel plan, and a browser map. Cold requests use two location geocodes and one directions call; station coordinates are prepared offline from the supplied CSV. The README explains initial fuel pricing, centroid limitations, optimization, reproducible setup, and test results.

Please import `postman/Spotter-Fuel-Route-API.postman_collection.json` and set `base_url` to the live API. If the GitHub repository is private, I will grant access to the reviewer account you specify. Render free-tier startup can delay the first request.

Thank you,
Sohaib

## Before sending

- Replace all three URL placeholders and grant private-repository access as needed.
- Deploy the committed `render.yaml` with a real ORS key and production secret.
- Verify live health, route, Swagger, and the returned map URL.
- Record the walkthrough in `docs/LOOM_SCRIPT.md` within five minutes.

## Publishing from this workspace

GitHub CLI was not available during implementation. After installing it, run:

```bash
gh auth login
gh repo create spotter-fuel-route-api --private --source=. --remote=origin --push
```

These commands create the new assessment repository; if GitHub reports that the name is already taken, inspect ownership/content before adding any remote or pushing.
