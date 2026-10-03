"""Optional live verification; intentionally outside the normal unit test suite."""

import argparse
import json
from pathlib import Path
from time import perf_counter

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--start", default="Dallas, TX")
    parser.add_argument("--finish", default="Los Angeles, CA")
    args = parser.parse_args()
    results = []
    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=120, trust_env=False) as client:
        health = client.get("/health/")
        health.raise_for_status()
        for attempt in range(2):
            started = perf_counter()
            response = client.post("/api/v1/route/", json={"start": args.start, "finish": args.finish})
            elapsed = perf_counter() - started
            if response.status_code != 200:
                raise RuntimeError(f"Route failed ({response.status_code}): {response.text}")
            plan = response.json()
            assert plan["route"]["geometry"]["type"] == "LineString"
            assert plan["fuel"]["longest_leg_miles"] <= 500
            assert all(0 < stop["gallons_purchased"] <= 50 for stop in plan["fuel_stops"])
            bought = plan["initial_fueling"]["gallons_purchased"] + sum(
                s["gallons_purchased"] for s in plan["fuel_stops"]
            )
            assert abs(bought - plan["fuel"]["estimated_gallons_consumed"]) < 0.001
            assert client.get(plan["map_url"]).status_code == 200
            results.append(
                {
                    "attempt": attempt + 1,
                    "seconds": round(elapsed, 4),
                    "distance_miles": plan["route"]["distance_miles"],
                    "fuel_stops": len(plan["fuel_stops"]),
                    "fuel": plan["fuel"],
                }
            )
        assert results[0]["fuel"] == results[1]["fuel"]
        assert client.get("/api/docs/").status_code == 200
        assert client.get("/api/schema/").status_code == 200
        assert client.post("/api/v1/route/", json={"start": "", "finish": args.finish}).status_code == 400
    output = Path("artifacts")
    output.mkdir(exist_ok=True)
    (output / "smoke-response.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {"health": health.json(), "start": args.start, "finish": args.finish, "runs": results}, indent=2
        )
    )


if __name__ == "__main__":
    main()
