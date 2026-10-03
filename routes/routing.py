import hashlib
import json
import math

import httpx
from django.conf import settings
from django.core.cache import cache
from pyproj import Geod

from .errors import RouteError

GEOD = Geod(ellps="WGS84")
BASE_URL = "https://api.heigit.org"


def coordinates(value: object) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        raise ValueError("Missing coordinates")
    lon, lat = float(value[0]), float(value[1])
    if not math.isfinite(lon + lat) or not -180 <= lon <= 180 or not -90 <= lat <= 90:
        raise ValueError("Invalid coordinates")
    return lon, lat


class RoutingClient:
    def __init__(self, client: httpx.Client):
        self.client = client

    def request(self, method: str, path: str, **kwargs) -> dict:
        if not settings.ORS_API_KEY:
            raise RouteError("ORS_API_KEY is not configured.", "provider_not_configured", 503)
        try:
            response = self.client.request(
                method, BASE_URL + path, headers={"Authorization": settings.ORS_API_KEY}, **kwargs
            )
            if response.status_code == 429:
                raise RouteError("Routing provider quota exceeded. Try later.", "upstream_quota", 503)
            if response.status_code in (400, 404):
                raise RouteError("The provider cannot resolve or route these locations.", "unsupported_route")
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("Expected JSON object")
            return data
        except httpx.TimeoutException as exc:
            raise RouteError("Routing provider timed out.", "upstream_timeout", 504) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise RouteError("Routing provider returned an invalid response.", "upstream_error", 502) from exc

    def geocode(self, query: str) -> dict:
        key = "geocode:v1:" + hashlib.sha256(query.casefold().encode()).hexdigest()
        if (result := cache.get(key)) is not None:
            return result
        data = self.request("GET", "/pelias/v1/search", params={"text": query, "size": 1})
        try:
            if not data["features"]:
                raise RouteError(f"Location could not be resolved: {query}", "location_not_found")
            feature = data["features"][0]
            properties = feature["properties"]
            if not isinstance(properties, dict):
                raise ValueError("Invalid geocoding properties")
            country = str(properties.get("country_a", "")).upper()
            if country not in ("USA", "US"):
                raise RouteError("Both locations must resolve within the United States.", "non_us_location")
            confidence = float(properties.get("confidence", 1))
            if not math.isfinite(confidence) or confidence < 0.6:
                raise RouteError(
                    "Location match is ambiguous; provide a more specific US address.", "ambiguous_location"
                )
            if feature["geometry"]["type"] != "Point":
                raise ValueError("Invalid geocoding geometry type")
            lon, lat = coordinates(feature["geometry"]["coordinates"])
            result = {"query": query, "latitude": lat, "longitude": lon}
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise RouteError("Malformed upstream geocoding response.", "upstream_error", 502) from exc
        cache.set(key, result, 86400)
        return result

    def directions(self, start: dict, finish: dict) -> dict:
        a = [start["longitude"], start["latitude"]]
        b = [finish["longitude"], finish["latitude"]]
        if GEOD.inv(*a, *b)[2] < 100:
            raise RouteError("Start and finish must be at least 100 meters apart.", "same_location", 400)
        key = "directions:v1:" + hashlib.sha256(json.dumps([a, b]).encode()).hexdigest()
        if (result := cache.get(key)) is not None:
            return result
        data = self.request(
            "POST",
            "/openrouteservice/v2/directions/driving-car/geojson",
            json={"coordinates": [a, b], "instructions": False, "options": {"avoid_borders": "all"}},
        )
        try:
            feature = data["features"][0]
            geometry = feature["geometry"]
            if geometry["type"] != "LineString" or len(geometry["coordinates"]) < 2:
                raise ValueError("Invalid route geometry")
            coords = [list(coordinates(point)) for point in geometry["coordinates"]]
            summary = feature["properties"]["summary"]
            distance, duration = float(summary["distance"]), float(summary["duration"])
            if not math.isfinite(distance + duration) or distance <= 0 or duration <= 0:
                raise ValueError("Invalid route summary")
            geometry_length = sum(GEOD.inv(*p, *q)[2] for p, q in zip(coords, coords[1:], strict=False))
            if geometry_length <= 0 or geometry_length > distance * 1.02 + 50:
                raise ValueError("Route summary understates geometry distance")
            if GEOD.inv(*a, *coords[0])[2] > 2000 or GEOD.inv(*b, *coords[-1])[2] > 2000:
                raise RouteError("Provider snapped an endpoint more than 2 km away.", "unsupported_route")
            result = {
                "distance_meters": distance,
                "duration_seconds": duration,
                "geometry": {"type": "LineString", "coordinates": coords},
            }
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise RouteError("Malformed upstream directions response.", "upstream_error", 502) from exc
        cache.set(key, result, settings.CACHE_TTL)
        return result
