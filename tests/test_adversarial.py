import json
from dataclasses import replace
from decimal import Decimal

import httpx
import pytest

from routes.errors import RouteError
from routes.optimization import optimize
from routes.routing import RoutingClient
from routes.stations import Candidate
from tests.test_routing import FINISH, START, directions_response, geocode_response


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        3,
        {"features": [None]},
        {"features": [{"properties": None}]},
        {"features": [{"properties": ["USA"]}]},
    ],
)
def test_malformed_geocode_structures(payload):
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload))) as http:
        with pytest.raises(RouteError) as exc:
            RoutingClient(http).geocode("Dallas")
        assert exc.value.status_code == 502


def test_ambiguous_geocode_match():
    payload = geocode_response()
    payload["features"][0]["properties"]["confidence"] = 0.2
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload))) as http:
        with pytest.raises(RouteError) as exc:
            RoutingClient(http).geocode("Unknown street somewhere")
        assert exc.value.get_codes() == "ambiguous_location"


@pytest.mark.parametrize("distance", [-10, 0, 1400, float("nan"), float("inf")])
def test_invalid_route_distance(distance):
    payload = directions_response()
    payload["features"][0]["properties"]["summary"]["distance"] = distance
    with httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text=json.dumps(payload)))
    ) as http:
        with pytest.raises(RouteError) as exc:
            RoutingClient(http).directions(START, FINISH)
        assert exc.value.status_code == 502


def test_directions_cache_independent_of_optimizer():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=directions_response())

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        client = RoutingClient(http)
        assert client.directions(START, FINISH) == client.directions(START, FINISH)
    assert len(calls) == 1


def test_remove_unneeded_stop_and_its_detour(index):
    initial = replace(index.stations[0], price=Decimal("2"))
    stations = [
        Candidate(replace(initial, record_id="a", price=Decimal("5")), 200, 1),
        Candidate(replace(initial, record_id="b", price=Decimal("3")), 450, 1),
    ]
    plan = optimize(stations, 700, initial)
    assert len(plan["fuel_stops"]) == 1
    assert plan["fuel"]["estimated_driving_miles_including_detours"] == 702
    assert plan["fuel"]["estimated_gallons_consumed"] == 70.2


def test_fractional_gallons_cost_conservation(index):
    plan = optimize([Candidate(index.stations[1], 450.12345, 1.23456)], 777.98765, index.stations[0])
    expected_distance = 777.98765 + 2 * 1.23456
    assert plan["fuel"]["estimated_gallons_consumed"] == round(expected_distance / 10, 4)
    assert plan["fuel"]["longest_leg_miles"] <= 500
    purchase = plan["initial_fueling"]["gallons_purchased"] + plan["fuel_stops"][0]["gallons_purchased"]
    assert purchase == pytest.approx(expected_distance / 10, abs=0.0001)


def test_map_escapes_untrusted_station_name(api):
    import uuid

    from django.core.cache import cache

    route_id = uuid.uuid4()
    cache.set(f"map:{route_id}", {"fuel_stops": [{"name": "</script><script>alert(1)</script>"}]})
    response = api.get(f"/api/v1/route/{route_id}/map/")
    assert response.status_code == 200
    assert b"</script><script>alert(1)</script>" not in response.content
    assert b"\\u003C/script\\u003E" in response.content
