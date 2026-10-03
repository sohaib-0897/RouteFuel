import httpx
import pytest

from routes.errors import RouteError
from routes.routing import BASE_URL, RoutingClient

START = {"query": "Dallas, TX", "longitude": -96.797, "latitude": 32.7767}
FINISH = {"query": "Los Angeles, CA", "longitude": -118.2437, "latitude": 34.0522}


def geocode_response(lon=-96.797, lat=32.7767, country="USA"):
    return {
        "features": [
            {"geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": {"country_a": country}}
        ]
    }


def directions_response():
    return {
        "features": [
            {
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [-96.797, 32.7767],
                        [-102.0779, 31.9973],
                        [-106.485, 31.7619],
                        [-112.074, 33.4484],
                        [-118.2437, 34.0522],
                    ],
                },
                "properties": {"summary": {"distance": 2253081.6, "duration": 72000}},
            }
        ]
    }


def test_current_endpoints_and_cache():
    requests = []

    def handler(request):
        requests.append(request)
        assert request.url.host == "api.heigit.org"
        assert request.headers["Authorization"] == "mock-key"
        return httpx.Response(200, json=geocode_response())

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        client = RoutingClient(http)
        assert client.geocode("Dallas")["latitude"] == 32.7767
        assert client.geocode("DALLAS")["longitude"] == -96.797
    assert len(requests) == 1
    assert requests[0].url.path == "/pelias/v1/search"


def test_one_directions_call_and_lon_lat_order():
    import json

    def handler(request):
        assert request.method == "POST"
        assert request.url.path == "/openrouteservice/v2/directions/driving-car/geojson"
        body = json.loads(request.content)
        assert body["coordinates"] == [[-96.797, 32.7767], [-118.2437, 34.0522]]
        assert body["options"]["avoid_borders"] == "all"
        return httpx.Response(200, json=directions_response())

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        assert RoutingClient(http).directions(START, FINISH)["distance_meters"] == 2253081.6


@pytest.mark.parametrize(
    "payload,code",
    [
        ({"features": []}, "location_not_found"),
        (geocode_response(country="CAN"), "non_us_location"),
        ({}, "upstream_error"),
        (geocode_response(lon=999), "upstream_error"),
        (geocode_response(lat=float("nan")), "upstream_error"),
    ],
)
def test_geocoding_validation(payload, code):
    # Serialize NaN manually because httpx correctly refuses invalid JSON floats.
    import json

    with httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text=json.dumps(payload)))
    ) as http:
        with pytest.raises(RouteError) as exc:
            RoutingClient(http).geocode("invalid")
        assert exc.value.get_codes() == code


@pytest.mark.parametrize("status,expected", [(429, 503), (401, 502), (503, 502), (404, 422)])
def test_http_errors(status, expected):
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(status, json={}))) as http:
        with pytest.raises(RouteError) as exc:
            RoutingClient(http).geocode("Dallas")
        assert exc.value.status_code == expected


def test_timeout_does_not_retry():
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("test timeout")

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(RouteError) as exc:
            RoutingClient(http).geocode("Dallas")
        assert exc.value.status_code == 504
        assert len(calls) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"features": []},
        {"features": [{}]},
        {"features": [{"geometry": {"type": "Point", "coordinates": []}}]},
    ],
)
def test_malformed_directions(payload):
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload))) as http:
        with pytest.raises(RouteError) as exc:
            RoutingClient(http).directions(START, FINISH)
        assert exc.value.status_code == 502


def test_same_resolved_location_rejected():
    with httpx.Client(transport=httpx.MockTransport(lambda r: pytest.fail("No network expected"))) as http:
        with pytest.raises(RouteError) as exc:
            RoutingClient(http).directions(START, START)
        assert exc.value.status_code == 400


def test_missing_key(settings):
    settings.ORS_API_KEY = ""
    with httpx.Client() as http:
        with pytest.raises(RouteError) as exc:
            RoutingClient(http).geocode("Dallas")
        assert exc.value.status_code == 503


def test_bad_json():
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, text="<html>"))) as http:
        with pytest.raises(RouteError) as exc:
            RoutingClient(http).request("GET", "/pelias/v1/search")
        assert exc.value.status_code == 502


def test_base_url():
    assert BASE_URL == "https://api.heigit.org"
