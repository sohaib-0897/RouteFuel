"""Capture real routes or compare against the protected backend's live capture."""

import argparse
import json
import time
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--output", required=True)
    parser.add_argument("--compare")
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    summary = []
    for name, finish in [("dallas-la", "Los Angeles, CA"), ("dallas-austin", "Austin, TX")]:
        times = []
        plan = None
        for _ in range(2):
            started = time.perf_counter()
            response = httpx.post(
                args.base_url + "/api/v1/route/",
                json={"start": "Dallas, TX", "finish": finish},
                timeout=110,
                trust_env=False,
            )
            times.append(round(time.perf_counter() - started, 4))
            response.raise_for_status()
            plan = response.json()
        (output / (name + ".json")).write_text(json.dumps(plan), encoding="utf-8")
        if args.compare:
            baseline = json.loads((Path(args.compare) / (name + ".json")).read_text(encoding="utf-8"))
            for field in (
                "start",
                "finish",
                "route",
                "vehicle",
                "fuel_stops",
                "initial_fueling",
                "fuel",
                "optimization",
                "warnings",
            ):
                assert plan[field] == baseline[field], f"{name}: {field} changed"
        summary.append(
            {"route": name, "seconds": times, "fuel": plan["fuel"], "stops": len(plan["fuel_stops"])}
        )
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
