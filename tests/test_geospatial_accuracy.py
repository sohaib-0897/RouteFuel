import csv
import io
from collections import Counter
from dataclasses import replace
from decimal import Decimal

import pytest
from shapely.geometry import Point
from shapely.strtree import STRtree

from routes.addresses import classify_address, match_rejection, normalize_census_address
from routes.errors import RouteError
from routes.optimization import optimize
from routes.preprocessing import parse_census, prepare, read_source
from routes.routing import GEOD
from routes.stations import PROJECT, Candidate
from tests.test_preprocessing import ROW, census_response, write_source, zip_centroids


@pytest.mark.parametrize(
    "address,category",
    [
        ("1323 E MAIN ST", "conventional_street"),
        ("I-44, EXIT 283 & US-69", "exit_description"),
        ("34 MILE WEST OF EXIT 11/146", "exit_description"),
        ("US-13 & US-40", "intersection"),
        ("US-50/US-77", "intersection"),
        ("M-57", "highway_interstate"),
        ("NJTP MM 5 SB", "highway_interstate"),
        (",", "malformed_partial"),
        ("LINCOLN HWY", "other"),
    ],
)
def test_address_classification(address, category):
    assert classify_address(address) == category


@pytest.mark.parametrize(
    "original,query",
    [
        (" 100  Main Street. ", "100 MAIN ST"),
        ("I-44, EXIT 283 & US-69", "INTERSTATE 44 & US HIGHWAY 69"),
        ("I-35 & FISHER RD, EXIT 144", "INTERSTATE 35 & FISHER RD"),
        ("I-40, EXIT 77", "INTERSTATE 40 EXIT 77"),
        ("1-40 EXIT 77", "INTERSTATE 40 EXIT 77"),
        ("US-24 & SR-27", "US HIGHWAY 24 & STATE HIGHWAY 27"),
        ("CR-X61", "COUNTY ROAD X61"),
        ("US-45 ALT", "US HIGHWAY 45 ALT"),
    ],
)
def test_query_normalization_without_inventing_addresses(original, query):
    assert normalize_census_address(original) == query
    assert normalize_census_address(query) == query


@pytest.mark.parametrize(
    "source,city,match,reason",
    [
        ("I-65, EXIT 219 & CR-42", "Jemison", "219 CO RD 42, JEMISON, AL, 35085", "invented_house_number"),
        ("US-169 & SR-25", "Belle Plaine", "US HWY 169 & HWY 25, MOUNTAIN IRON, MN, 55768", "different_city"),
        ("100 MAIN ST", "Dallas", "101 MAIN ST, DALLAS, TX, 75001", "changed_house_number"),
        ("I-15 & US-2", "Shelby", "15TH AVE & US HWY 2, SHELBY, MT, 59474", "changed_road_identifier"),
        ("US-50 & US-77", "Florence", "US HWY 50 & US HWY 77, FLORENCE, KS, 66851", None),
    ],
)
def test_census_match_checks(source, city, match, reason):
    assert match_rejection(source, city, match) == reason


def test_false_census_house_number_downgrades_to_city_fallback(tmp_path):
    source = tmp_path / "raw.csv"
    write_source(source, [["1", "Truck Stop", "I-35, EXIT 100 & US-80", "Dallas", "TX", "1", "3"]])
    records, _ = read_source(source)
    rejected = Counter()
    assert parse_census(census_response(records), records, rejected) == {}
    assert rejected["invented_house_number"] == 1


def test_preprocessing_preserves_quality_and_original_description(tmp_path):
    import hashlib

    source, cache_dir, output = tmp_path / "raw.csv", tmp_path / "cache", tmp_path / "processed.csv"
    write_source(source, [ROW, ["2", "Highway Stop", "I-35, EXIT 100 & US-80", "Dallas", "TX", "1", "3"]])
    original = source.read_bytes()
    records, _ = read_source(source)
    cache_dir.mkdir()
    (cache_dir / "geonames-US.zip").write_bytes(zip_centroids())
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["1", "input", "Match", "Exact", "100 MAIN ST, DALLAS, TX, 75001", "-96.797,32.7767"])
    writer.writerow(["2", "input", "No_Match"])
    (cache_dir / f"census-{hashlib.sha256(original).hexdigest()}.csv").write_text(
        stream.getvalue(), newline=""
    )
    stats = prepare(source, output, cache_dir, offline=True)
    with output.open(newline="") as file:
        prepared = list(csv.DictReader(file))
    assert [row["geocoding_source"] for row in prepared] == ["census", "city_centroid"]
    assert prepared[1]["address"] == records[1]["address"]
    assert source.read_bytes() == original
    assert stats["census"] == stats["city_centroid"] == 1


def station(index, identity, quality, price):
    return replace(
        index.stations[0], record_id=identity, name=identity, geocoding_source=quality, price=Decimal(price)
    )


def test_competitive_accurate_stop_wins_and_penalty_is_not_billed(index):
    exact = Candidate(station(index, "accurate", "census", "3.1"), 400, 0)
    approximate = Candidate(station(index, "approximate", "city_centroid", "3"), 400, 5, 0)
    plan = optimize([approximate, exact], 800, index.stations[0])
    assert [stop["name"] for stop in plan["fuel_stops"]] == ["accurate"]
    assert plan["fuel"]["estimated_fuel_cost_usd"] == 40 * 3.5 + 40 * 3.1
    assert plan["optimization"]["quality_penalty_included_in_fuel_cost"] is False
    assert plan["fuel_stops"][0]["detour_basis"] == "geodesic_road_access_estimate"
    assert plan["fuel_stops"][0]["location_is_approximate"] is False
    assert plan["fuel_stops"][0]["detour_is_estimated"] is True


def test_very_cheap_centroid_has_no_false_zero_access_range_advantage(index):
    exact = Candidate(station(index, "accurate", "census", "5"), 499, 0)
    # Even a caller supplying a bogus zero side-distance cannot erase the budget.
    approximate = Candidate(station(index, "approximate", "city_centroid", "0.1"), 499, 0, 0)
    plan = optimize([approximate, exact], 900, index.stations[0])
    assert [stop["name"] for stop in plan["fuel_stops"]] == ["accurate"]
    assert plan["fuel"]["longest_leg_miles"] <= 500
    with pytest.raises(RouteError):
        optimize([approximate], 900, index.stations[0])


def test_centroids_preserve_feasibility_with_budget_and_unbilled_penalty(index):
    candidates = [
        Candidate(station(index, str(mile), "city_centroid", "3"), mile, 5, 0) for mile in (400, 800, 1200)
    ]
    plan = optimize(candidates, 1500, index.stations[0])
    assert len(plan["fuel_stops"]) == 3
    assert all(stop["location_is_approximate"] and stop["detour_is_estimated"] for stop in plan["fuel_stops"])
    assert all(stop["detour_basis"] == "city_centroid_uncertainty_budget" for stop in plan["fuel_stops"])
    assert all(stop["detour_miles"] == 10 for stop in plan["fuel_stops"])
    assert plan["fuel"]["longest_leg_miles"] <= 500
    assert plan["fuel"]["estimated_gallons_consumed"] == 153
    actual = plan["initial_fueling"]["estimated_cost"] + sum(s["estimated_cost"] for s in plan["fuel_stops"])
    assert actual == pytest.approx(plan["fuel"]["estimated_fuel_cost_usd"], abs=0.02)


def test_coordinate_quality_can_change_choice_and_cache_policy_input(index):
    exact = Candidate(station(index, "accurate", "census", "3.1"), 400, 0)
    approximate = Candidate(station(index, "approximate", "city_centroid", "3"), 400, 5, 0)
    zero = optimize([exact, approximate], 800, index.stations[0], centroid_penalty_usd=Decimal(0))
    normal = optimize([exact, approximate], 800, index.stations[0])
    assert zero["fuel_stops"][0]["name"] == "approximate"
    assert normal["fuel_stops"][0]["name"] == "accurate"


def rebuild(index, stations):
    index.stations = stations
    index.points = [Point(*PROJECT.transform(s.longitude, s.latitude)) for s in stations]
    index.tree = STRtree(index.points)


def test_city_30_miles_from_route_remains_candidate_without_fake_nearby_claim(index):
    lon, lat, _ = GEOD.fwd(-99, 33, 0, 30 * 1609.344)
    base = index.stations[0]
    centroid = replace(base, longitude=lon, latitude=lat, geocoding_source="city_centroid")
    exact = replace(centroid, record_id="different", geocoding_source="census")
    rebuild(index, [centroid, exact])
    # Insert the true comparison point as a route vertex to avoid arc ambiguity.
    geometry = {"coordinates": [[-100, 33], [-99, 33], [-98, 33]]}
    candidates = index.candidates(
        geometry, 200, 15, 20, centroid_corridor_miles=35, centroid_max_detour_miles=110
    )
    assert len(candidates) == 1
    selected = candidates[0]
    assert selected.station.geocoding_source == "city_centroid"
    assert selected.centroid_to_route_miles == pytest.approx(30, abs=0.01)
    assert selected.side_miles * 2 == pytest.approx(94, abs=0.03)


def test_broad_city_tolerance_still_has_limit(index):
    lon, lat, _ = GEOD.fwd(-99, 33, 0, 36 * 1609.344)
    rebuild(
        index, [replace(index.stations[0], longitude=lon, latitude=lat, geocoding_source="city_centroid")]
    )
    assert (
        index.candidates(
            {"coordinates": [[-100, 33], [-99, 33], [-98, 33]]},
            200,
            15,
            20,
            centroid_corridor_miles=35,
            centroid_max_detour_miles=110,
        )
        == []
    )


def test_initial_price_reference_prefers_close_accurate_coordinate(index):
    centroid = replace(index.stations[0], geocoding_source="city_centroid")
    lon, lat, _ = GEOD.fwd(centroid.longitude, centroid.latitude, 90, 4 * 1609.344)
    exact = replace(centroid, record_id="exact", geocoding_source="census", longitude=lon, latitude=lat)
    rebuild(index, [centroid, exact])
    selected, miles = index.initial_price(centroid.longitude, centroid.latitude)
    assert selected.record_id == "exact"
    assert miles == pytest.approx(4)


def test_policy_changes_invalidate_plan_but_reuse_provider_cache(api, settings):
    from unittest.mock import patch

    import httpx

    from tests.test_api import handler

    calls = []
    real_client = httpx.Client

    def transport(request):
        calls.append(request)
        return handler(request)

    def factory(**kwargs):
        return real_client(transport=httpx.MockTransport(transport), **kwargs)

    payload = {"start": "Dallas, TX", "finish": "Los Angeles, CA"}
    with patch("routes.service.httpx.Client", side_effect=factory):
        first = api.post("/api/v1/route/", payload, format="json")
        assert first.status_code == 200
        assert len(calls) == 3
        settings.CENTROID_STOP_PENALTY_USD = 30
        second = api.post("/api/v1/route/", payload, format="json")
        assert second.status_code == 200
        assert second.json()["optimization"]["centroid_stop_penalty_usd"] == 30
        assert len(calls) == 3
        with patch("routes.service.httpx.Client", side_effect=AssertionError("cached request")):
            assert api.post("/api/v1/route/", payload, format="json").status_code == 200
