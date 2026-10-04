"""Bounded US place search; independent of verified route/geocode caches."""

import hashlib

import httpx
from django.core.cache import cache
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from .errors import RouteError
from .routing import RoutingClient, coordinates


class LocationSearchSerializer(serializers.Serializer):
    q = serializers.CharField(min_length=2, max_length=120, trim_whitespace=True)


class PlaceSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    context = serializers.CharField()
    query = serializers.CharField()


class LocationResultsSerializer(serializers.Serializer):
    results = PlaceSerializer(many=True)


def search_locations(query: str) -> list[dict]:
    key = "autocomplete:v1:" + hashlib.sha256(query.casefold().encode()).hexdigest()
    if (cached := cache.get(key)) is not None:
        return cached
    with httpx.Client(timeout=httpx.Timeout(8, connect=3), trust_env=False) as http:
        data = RoutingClient(http).request(
            "GET",
            "/pelias/v1/autocomplete",
            params={"text": query, "boundary.country": "USA", "layers": "locality,venue,address", "size": 8},
        )
    features = data.get("features")
    if not isinstance(features, list):
        raise RouteError("Invalid place search response. Try again.", "upstream_error", 502)
    results, seen = [], set()
    for feature in features[:8]:
        try:
            props = feature["properties"]
            if str(props.get("country_a", "")).upper() not in ("US", "USA"):
                continue
            if feature["geometry"]["type"] != "Point":
                continue
            coordinates(feature["geometry"]["coordinates"])
            name = props.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            name = name.strip()[:160]
            locality = props.get("locality", "")
            region = props.get("region", props.get("region_a", ""))
            region_code = props.get("region_a", region)
            if not all(isinstance(v, str) for v in (locality, region, region_code)):
                continue
            # City results get useful context, while venues keep their name prominent.
            context = ", ".join(dict.fromkeys(v for v in (locality or name, region) if v))
            if props.get("layer") == "address":
                context = ", ".join(v for v in (locality, region) if v) or "United States"
            route_query = ", ".join(dict.fromkeys(v for v in (name, locality, region_code) if v))
            if not region_code:
                route_query += ", United States"
            identity = (name.casefold(), context.casefold())
            if identity in seen or len(route_query) > 300:
                continue
            seen.add(identity)
            results.append(
                {
                    "id": str(props.get("gid", len(results))),
                    "name": name,
                    "context": context,
                    "query": route_query,
                }
            )
            if len(results) == 6:
                break
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
    cache.set(key, results, 3600)
    return results


class LocationSearchView(APIView):
    @extend_schema(parameters=[LocationSearchSerializer], responses={200: LocationResultsSerializer})
    def get(self, request):
        serializer = LocationSearchSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        return Response({"results": search_locations(serializer.validated_data["q"])})
