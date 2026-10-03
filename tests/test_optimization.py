import itertools
from dataclasses import replace
from decimal import Decimal

import pytest

from routes.errors import RouteError
from routes.optimization import Node, leg_distance, optimize, purchase_on_path
from routes.stations import Candidate


def candidate(index, mile, price="3.0", side=0, identity="extra"):
    return Candidate(replace(index.stations[0], price=Decimal(price), record_id=identity), mile, side)


@pytest.mark.parametrize("distance", [1, 100, 499.999, 500])
def test_short_trip_fuel_is_not_free(index, distance):
    plan = optimize([], distance, index.stations[0])
    assert plan["fuel_stops"] == []
    assert plan["fuel"]["estimated_gallons_consumed"] == round(distance / 10, 4)
    assert plan["fuel"]["estimated_fuel_cost_usd"] == round(distance / 10 * 3.5, 2)
    assert plan["initial_fueling"]["gallons_purchased"] == round(distance / 10, 4)


def test_slightly_over_range_requires_stop(index):
    plan = optimize([candidate(index, 400)], 500.01, index.stations[0])
    assert len(plan["fuel_stops"]) == 1
    assert plan["fuel"]["longest_leg_miles"] <= 500
    with pytest.raises(RouteError, match="No feasible"):
        optimize([], 500.01, index.stations[0])


def test_long_trip_multiple_stops_and_conservation(index):
    stations = [
        candidate(index, mile, price, identity=str(mile))
        for mile, price in [(400, "3"), (800, "4"), (1200, "2.8"), (1600, "3.2")]
    ]
    plan = optimize(stations, 2000, index.stations[0])
    assert len(plan["fuel_stops"]) == 4
    purchases = plan["initial_fueling"]["gallons_purchased"] + sum(
        s["gallons_purchased"] for s in plan["fuel_stops"]
    )
    assert purchases == pytest.approx(200)
    assert plan["fuel"]["longest_leg_miles"] <= 500
    assert plan["fuel"]["estimated_arrival_fuel_gallons"] == 0
    assert all(0 < s["gallons_purchased"] <= 50 for s in plan["fuel_stops"])


def test_boundary_includes_station_access(index):
    plan = optimize([candidate(index, 499, side=1)], 800, index.stations[0])
    assert plan["fuel"]["longest_leg_miles"] == 500
    assert plan["fuel"]["estimated_driving_miles_including_detours"] == 802
    with pytest.raises(RouteError, match="No feasible"):
        optimize([candidate(index, 499.01, side=1)], 800, index.stations[0])


def test_lower_price_changes_choice(index):
    plan = optimize(
        [candidate(index, 400, "5", identity="expensive"), candidate(index, 410, "2", identity="cheap")],
        800,
        index.stations[0],
    )
    assert [s["retail_price_per_gallon"] for s in plan["fuel_stops"]] == [2]
    assert plan["fuel"]["estimated_fuel_cost_usd"] == 41 * 3.5 + 39 * 2


def test_detour_can_make_cheap_station_unreachable(index):
    plan = optimize(
        [candidate(index, 495, "1", side=6), candidate(index, 400, "3", identity="reachable")],
        800,
        index.stations[0],
    )
    assert plan["fuel_stops"][0]["retail_price_per_gallon"] == 3


def test_greedy_carries_cheaper_fuel():
    path = [
        Node(0, 0, Decimal("2"), None),
        Node(400, 0, Decimal("5"), None),
        Node(800, 0, Decimal("0"), None),
    ]
    purchases, _ = purchase_on_path(path)
    assert purchases == [Decimal(50), Decimal(30)]
    assert sum(g * n.price for g, n in zip(purchases, path, strict=False)) == 250


def test_fixed_path_greedy_against_exhaustive_integer_fuel():
    # Scale discrete fuel miles to 100-mile units. Independently enumerate every
    # legal purchase combination, rather than reproducing the greedy rule.
    prices = [Decimal("4"), Decimal("2"), Decimal("5"), Decimal("3")]
    path = [Node(i * 200, 0, p, None) for i, p in enumerate(prices)] + [Node(800, 0, Decimal(0), None)]
    actual, _ = purchase_on_path(path)
    possible = []
    for buys in itertools.product(range(6), repeat=4):
        inventory = 0
        for buy in buys:
            inventory += buy
            if not 2 <= inventory <= 5:
                break
            inventory -= 2
        else:
            if inventory == 0:
                possible.append(sum(Decimal(b * 10) * p for b, p in zip(buys, prices, strict=True)))
    assert sum(g * p for g, p in zip(actual, prices, strict=True)) == min(possible)


def test_deterministic_with_reversed_candidates(index):
    candidates = [candidate(index, 250, "3", identity="a"), candidate(index, 450, "3", identity="b")]
    assert optimize(candidates, 700, index.stations[0]) == optimize(
        list(reversed(candidates)), 700, index.stations[0]
    )


def test_gap_cannot_be_hidden_by_rounding(index):
    with pytest.raises(RouteError):
        optimize([candidate(index, 500.0001)], 999, index.stations[0])


def test_leg_math():
    assert leg_distance(Node(100, 2, Decimal(3), None), Node(450, 4, Decimal(2), None)) == 356
