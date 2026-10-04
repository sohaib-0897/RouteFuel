from dataclasses import dataclass
from decimal import Decimal

from .constants import MAX_RANGE, MPG
from .errors import RouteError
from .stations import Candidate, Station


@dataclass(frozen=True)
class Node:
    mile: float
    side: float
    price: Decimal
    station: Station | None
    centroid_to_route_miles: float | None = None


def leg_distance(a: Node, b: Node) -> float:
    return b.mile - a.mile + a.side + b.side


def optimize(
    candidates: list[Candidate],
    distance: float,
    initial: Station,
    *,
    centroid_penalty_usd: Decimal = Decimal("15"),
) -> dict:
    """DAG shortest path, then optimal fuel purchasing on that fixed itinerary.

    Path selection uses a just-enough-per-leg upper bound. Purchasing can improve
    it by carrying cheap fuel. Global path/fuel optimality is not claimed.
    """
    nodes = [Node(0, 0, initial.price, None)]
    nodes.extend(
        Node(
            c.route_mile,
            max(c.side_miles, 5.0) if c.station.geocoding_source == "city_centroid" else c.side_miles,
            c.station.price,
            c.station,
            c.centroid_to_route_miles,
        )
        for c in sorted(candidates, key=lambda c: (c.route_mile, c.station.record_id))
    )
    nodes.append(Node(distance, 0, Decimal(0), None))
    costs = [Decimal("Infinity")] * len(nodes)
    parents = [-1] * len(nodes)
    stops = [10**9] * len(nodes)
    costs[0], stops[0] = Decimal(0), 0
    for j in range(1, len(nodes)):
        for i in range(j - 1, -1, -1):
            if nodes[j].mile - nodes[i].mile > MAX_RANGE:
                break
            if nodes[j].mile <= nodes[i].mile or not costs[i].is_finite():
                continue
            miles = leg_distance(nodes[i], nodes[j])
            if miles > MAX_RANGE + 1e-9:
                continue
            value = costs[i] + Decimal(str(miles)) / Decimal(str(MPG)) * nodes[i].price
            if nodes[j].station is not None and nodes[j].station.geocoding_source == "city_centroid":
                value += centroid_penalty_usd
            count = stops[i] + (nodes[j].station is not None)
            if (value, count, i) < (costs[j], stops[j], parents[j]):
                costs[j], parents[j], stops[j] = value, i, count
    if parents[-1] < 0:
        raise RouteError(
            "No feasible station sequence within the 500-mile range and detour limits.",
            "no_feasible_fuel_plan",
        )
    path = [nodes[-1]]
    cursor = len(nodes) - 1
    while cursor:
        cursor = parents[cursor]
        path.append(nodes[cursor])
    path.reverse()
    # Remove zero-purchase visits and recompute purchasing without their detours.
    while True:
        purchases, legs = purchase_on_path(path)
        remove = {i for i in range(1, len(path) - 1) if purchases[i] <= Decimal("0.000000001")}
        if not remove:
            break
        path = [node for i, node in enumerate(path) if i not in remove]
    initial_gallons = purchases[0]
    initial_cost = initial_gallons * initial.price
    fuel_stops = []
    for i, node in enumerate(path[1:-1], 1):
        fuel_stops.append(
            {
                **node.station.public(),
                "sequence": i,
                "route_mile": round(node.mile, 2),
                "detour_miles": round(node.side * 2, 2),
                "detour_is_estimated": True,
                "detour_basis": (
                    "city_centroid_uncertainty_budget"
                    if node.station.geocoding_source == "city_centroid"
                    else "geodesic_road_access_estimate"
                ),
                **(
                    {"centroid_to_route_miles": round(node.centroid_to_route_miles, 2)}
                    if node.centroid_to_route_miles is not None
                    else {}
                ),
                "gallons_purchased": round(float(purchases[i]), 4),
                "estimated_cost": round(float(purchases[i] * node.price), 2),
            }
        )
    total_distance = sum(legs)
    total_cost = sum(
        (gallons * node.price for gallons, node in zip(purchases, path[:-1], strict=True)), Decimal(0)
    )
    return {
        "fuel_stops": fuel_stops,
        "initial_fueling": {
            "assumption": "Fuel loaded at origin, priced using a nearby accuracy-weighted dataset station; not a station visit.",
            "price_reference_station": initial.public(),
            "gallons_purchased": round(float(initial_gallons), 4),
            "estimated_cost": round(float(initial_cost), 2),
        },
        "fuel": {
            "estimated_driving_miles_including_detours": round(total_distance, 2),
            "estimated_gallons_consumed": round(total_distance / MPG, 4),
            "estimated_fuel_cost_usd": round(float(total_cost), 2),
            "estimated_arrival_fuel_gallons": 0,
            "longest_leg_miles": round(max(legs), 4),
        },
        "optimization": {
            "method": "cost-aware DAG itinerary followed by greedy fuel purchasing",
            "range_basis": "route miles plus estimated station access miles",
            "globally_optimal": False,
            "centroid_stop_penalty_usd": float(centroid_penalty_usd),
            "quality_penalty_included_in_fuel_cost": False,
        },
    }


def purchase_on_path(path: list[Node]) -> tuple[list[Decimal], list[float]]:
    """First reachable cheaper station: buy to reach it, else fill or reach finish.

    This exchange-rule greedy algorithm is optimal for a fixed itinerary and
    continuous fuel quantities, with no reserve and no transaction cost.
    """
    legs = [leg_distance(a, b) for a, b in zip(path, path[1:], strict=False)]
    if any(leg < 0 or leg > MAX_RANGE + 1e-9 for leg in legs):
        raise RouteError("Internal fuel plan violated the range constraint.", "invalid_fuel_plan", 500)
    purchases = []
    fuel_miles = Decimal(0)
    capacity = Decimal(str(MAX_RANGE))
    for i, node in enumerate(path[:-1]):
        travel = Decimal(0)
        target = capacity
        for j in range(i + 1, len(path)):
            travel += Decimal(str(legs[j - 1]))
            if travel > capacity + Decimal("0.000000001"):
                break
            if path[j].price < node.price or j == len(path) - 1:
                target = min(travel, capacity)
                break
        added = max(Decimal(0), target - fuel_miles)
        purchases.append(added / Decimal(str(MPG)))
        fuel_miles += added - Decimal(str(legs[i]))
        if fuel_miles < Decimal("-0.00000001") or fuel_miles > capacity:
            raise RouteError("Internal fuel inventory violation.", "invalid_fuel_plan", 500)
        fuel_miles = max(Decimal(0), fuel_miles)
    return purchases, legs
