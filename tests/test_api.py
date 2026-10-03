from unittest.mock import patch

import httpx
import pytest

from tests.test_routing import directions_response, geocode_response


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"start": "", "finish": "LA"},
        {"start": "  ", "finish": "LA"},
        {"start": "Dallas"},
        {"start": "Dallas", "finish": "dallas"},
        {"start": None, "finish": "LA"},
        {"start": 123, "finish": "LA"},
        {"start": ["Dallas"], "finish": "LA"},
        {"start": "x" * 301, "finish": "LA"},
    ],
)
def test_validation(api, payload):
    with patch("routes.service.httpx.Client") as http:
        assert api.post("/api/v1/route/", payload, format="json").status_code == 400
        http.assert_not_called()


def handler(request):
    if request.url.path.endswith("/search"):
        if "Dallas" in request.url.params["text"]:
            return httpx.Response(200, json=geocode_response())
        return httpx.Response(200, json=geocode_response(-118.2437, 34.0522))
    return httpx.Response(200, json=directions_response())


def test_integration_three_calls_cached_repeat_and_map(api):
    calls = []
    real_client = httpx.Client

    def transport(request):
        calls.append(request)
        return handler(request)

    def factory(**kwargs):
        return real_client(transport=httpx.MockTransport(transport), **kwargs)

    with patch("routes.service.httpx.Client", side_effect=factory):
        response = api.post(
            "/api/v1/route/", {"start": "Dallas, TX", "finish": "Los Angeles, CA"}, format="json"
        )
        assert response.status_code == 200, response.data
        plan = response.json()
        assert len(calls) == 3
        assert plan["route"]["distance_miles"] == 1400
        assert plan["route"]["geometry"]["type"] == "LineString"
        assert len(plan["fuel_stops"]) >= 2
        assert plan["fuel"]["longest_leg_miles"] <= 500
        assert plan["fuel"]["estimated_fuel_cost_usd"] > 0
        second = api.post(
            "/api/v1/route/", {"start": "Dallas, TX", "finish": "Los Angeles, CA"}, format="json"
        )
        assert second.status_code == 200
        assert len(calls) == 3
        assert second.json()["fuel"] == plan["fuel"]
        page = api.get(plan["map_url"])
        assert page.status_code == 200
        assert b"leaflet" in page.content
        assert b"mock-key" not in page.content


def test_health_no_upstream(api):
    with patch("httpx.Client", side_effect=AssertionError("No network")):
        response = api.get("/health/")
        assert response.status_code == 200
        assert response.json()["stations"] == 5


def test_missing_data_health_and_route(api, settings, tmp_path):
    settings.STATION_DATA_PATH = tmp_path / "missing.csv"
    assert api.get("/health/").status_code == 503
    response = api.post("/api/v1/route/", {"start": "Dallas", "finish": "LA"}, format="json")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "station_data_unavailable"


def test_expired_map(api):
    assert api.get("/api/v1/route/00000000-0000-0000-0000-000000000000/map/").status_code == 404


def test_schema_and_docs(api):
    response = api.get("/api/schema/")
    assert response.status_code == 200
    assert b"/api/v1/route/" in response.content
    assert api.get("/api/docs/").status_code == 200


def test_error_reaches_api(api):
    from routes.errors import RouteError

    with patch(
        "routes.views.plan_route", side_effect=RouteError("Provider timed out", "upstream_timeout", 504)
    ):
        response = api.post("/api/v1/route/", {"start": "Dallas", "finish": "LA"}, format="json")
        assert response.status_code == 504
        assert response.json()["error"]["code"] == "upstream_timeout"
