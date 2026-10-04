import copy
import hashlib
import json
import uuid
from decimal import Decimal

import httpx
from django.conf import settings
from django.core.cache import cache
from django.urls import reverse

from .constants import MAX_RANGE, METERS_PER_MILE, MPG
from .optimization import optimize
from .routing import RoutingClient
from .stations import station_index


def plan_route(start: str, finish: str) -> dict:
    index = station_index()
    key_data = [
        start.casefold(),
        finish.casefold(),
        index.fingerprint,
        settings.ROUTE_CORRIDOR_MILES,
        settings.MAX_DETOUR_MILES,
        settings.CENTROID_CORRIDOR_MILES,
        settings.CENTROID_MAX_DETOUR_MILES,
        settings.CENTROID_STOP_PENALTY_USD,
    ]
    key = "plan:v2:" + hashlib.sha256(json.dumps(key_data).encode()).hexdigest()
    result = cache.get(key)
    if result is None:
        with httpx.Client(timeout=httpx.Timeout(30, connect=5), trust_env=False) as http:
            client = RoutingClient(http)
            origin, destination = client.geocode(start), client.geocode(finish)
            route = client.directions(origin, destination)
        miles = route["distance_meters"] / METERS_PER_MILE
        initial, reference_distance = index.initial_price(origin["longitude"], origin["latitude"])
        candidates = index.candidates(
            route["geometry"],
            miles,
            settings.ROUTE_CORRIDOR_MILES,
            settings.MAX_DETOUR_MILES,
            centroid_corridor_miles=settings.CENTROID_CORRIDOR_MILES,
            centroid_max_detour_miles=settings.CENTROID_MAX_DETOUR_MILES,
        )
        plan = optimize(
            candidates, miles, initial, centroid_penalty_usd=Decimal(str(settings.CENTROID_STOP_PENALTY_USD))
        )
        plan["initial_fueling"]["reference_distance_miles"] = round(reference_distance, 2)
        result = {
            "start": origin,
            "finish": destination,
            "route": {
                "distance_miles": round(miles, 2),
                "duration_hours": round(route["duration_seconds"] / 3600, 2),
                "geometry": route["geometry"],
            },
            "vehicle": {
                "max_range_miles": MAX_RANGE,
                "fuel_economy_mpg": MPG,
                "tank_capacity_gallons": MAX_RANGE / MPG,
            },
            **plan,
            "warnings": [
                "Station access distances are estimates, not separately routed roads. Verify access before driving.",
                "Fuel prices are an assessment snapshot; availability and current prices are not verified.",
            ],
        }
        if any(s["geocoding_source"] == "city_centroid" for s in plan["fuel_stops"]):
            result["warnings"].append(
                "City-centroid stops are city-level candidates, not verified station coordinates. "
                "Their detour_miles are uncertainty budgets; confirm the actual stop and road access."
            )
        cache.set(key, result, settings.CACHE_TTL)
    result = copy.deepcopy(result)
    result["start"]["query"], result["finish"]["query"] = start, finish
    route_id = uuid.uuid4()
    result["map_url"] = reverse("route-map", kwargs={"route_id": route_id})
    result["map_expires_in_seconds"] = settings.CACHE_TTL
    cache.set(f"map:{route_id}", result, settings.CACHE_TTL)
    return result
