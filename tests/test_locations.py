"""Autocomplete must be US-only, bounded, cached, and isolated from routing."""

from unittest.mock import patch

import httpx
import pytest
from django.core.cache import cache

from routes.errors import RouteError
from routes.locations import search_locations


def feature(name="Dallas", country="USA", **props):
    return {
        "geometry": {"type": "Point", "coordinates": [-96.8, 32.8]},
        "properties": {
            "gid": "wof:locality:1",
            "name": name,
            "country_a": country,
            "locality": "Dallas",
            "region": "Texas",
            "region_a": "TX",
            "layer": "locality",
            **props,
        },
    }


def test_search_returns_name_context_and_route_query(api):
    with patch(
        "routes.locations.RoutingClient.request",
        return_value={"features": [feature(), feature("Dallas Love Field", layer="venue")]},
    ) as request:
        response = api.get("/api/v1/locations/", {"q": " Dallas "})
    assert response.status_code == 200
    assert response.json()["results"][0] == {
        "id": "wof:locality:1",
        "name": "Dallas",
        "context": "Dallas, Texas",
        "query": "Dallas, TX",
    }
    assert response.json()["results"][1]["query"] == "Dallas Love Field, Dallas, TX"
    assert request.call_args.kwargs["params"]["boundary.country"] == "USA"
    assert request.call_args.args[1] == "/pelias/v1/autocomplete"
    assert "mock-key" not in response.content.decode()


@pytest.mark.parametrize("query", ["", "a", " " * 3, "a" * 121])
def test_invalid_search_never_contacts_provider(api, query):
    with patch("routes.locations.RoutingClient.request") as request:
        assert api.get("/api/v1/locations/", {"q": query}).status_code == 400
        request.assert_not_called()


def test_search_filters_country_bad_features_and_duplicates():
    bad = feature("Invalid")
    bad["geometry"]["coordinates"] = [float("nan"), 30]
    with patch(
        "routes.locations.RoutingClient.request",
        return_value={
            "features": [feature(country="CAN"), bad, None, feature(), feature(), feature(name=42)]
        },
    ):
        assert len(search_locations("dallas")) == 1


def test_search_bounded_to_six():
    with patch(
        "routes.locations.RoutingClient.request",
        return_value={"features": [feature(str(n)) for n in range(20)]},
    ):
        assert len(search_locations("test")) == 6


def test_search_cache_does_not_seed_route_geocode_cache():
    with patch("routes.locations.RoutingClient.request", return_value={"features": [feature()]}) as request:
        assert search_locations("Dallas") == search_locations("dallas")
        assert request.call_count == 1
    assert not any(k.startswith("geocode:") for k in getattr(cache, "_cache", {}))


def test_invalid_response_is_visible(api):
    with patch("routes.locations.RoutingClient.request", return_value={"features": {}}):
        response = api.get("/api/v1/locations/", {"q": "Dallas"})
    assert response.status_code == 502


@pytest.mark.parametrize("status,code", [(503, "upstream_quota"), (504, "upstream_timeout")])
def test_search_propagates_safe_errors(api, status, code):
    with patch(
        "routes.locations.RoutingClient.request", side_effect=RouteError("Search unavailable.", code, status)
    ):
        response = api.get("/api/v1/locations/", {"q": "Dallas"})
    assert response.status_code == status
    assert response.json()["error"]["code"] == code


def test_provider_key_only_in_server_authorization_header():
    from routes.routing import RoutingClient

    def handler(request):
        assert request.headers["Authorization"] == "mock-key"
        assert "mock-key" not in str(request.url)
        assert request.url.params["boundary.country"] == "USA"
        return httpx.Response(200, json={"features": []})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = RoutingClient(client).request(
            "GET", "/pelias/v1/autocomplete", params={"text": "Dallas", "boundary.country": "USA"}
        )
    assert result == {"features": []}
