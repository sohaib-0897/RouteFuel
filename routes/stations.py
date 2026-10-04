import bisect
import csv
import hashlib
import math
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from pyproj import Transformer
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree

from .constants import METERS_PER_MILE, US_STATES
from .errors import RouteError
from .routing import GEOD, coordinates

PROJECT = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
UNPROJECT = Transformer.from_crs("EPSG:5070", "EPSG:4326", always_xy=True)


@dataclass(frozen=True)
class Station:
    record_id: str
    opis_truckstop_id: int
    name: str
    address: str
    city: str
    state: str
    price: Decimal
    longitude: float
    latitude: float
    geocoding_source: str

    def public(self) -> dict:
        return {
            "opis_truckstop_id": self.opis_truckstop_id,
            "name": self.name,
            "address": self.address,
            "city": self.city,
            "state": self.state,
            "longitude": self.longitude,
            "latitude": self.latitude,
            "retail_price_per_gallon": round(float(self.price), 4),
            "geocoding_source": self.geocoding_source,
            "location_is_approximate": self.geocoding_source == "city_centroid",
        }


@dataclass(frozen=True)
class Candidate:
    station: Station
    route_mile: float
    side_miles: float  # One-way access estimate, or centroid uncertainty budget.
    centroid_to_route_miles: float | None = None


class StationIndex:
    def __init__(self, path: Path):
        try:
            contents = path.read_bytes()
            self.fingerprint = hashlib.sha256(contents).hexdigest()
            with path.open(newline="", encoding="utf-8") as stream:
                records = list(csv.DictReader(stream))
            self.stations = []
            seen = set()
            for row in records:
                lon, lat = coordinates([row["longitude"], row["latitude"]])
                price = Decimal(row["price"])
                if (
                    row["state"] not in US_STATES
                    or not price.is_finite()
                    or not 0 < price < 100
                    or row["geocoding_source"] not in ("census", "city_centroid")
                    or not -180 <= lon <= -60
                    or not 18 <= lat <= 72
                ):
                    raise ValueError("Invalid processed station")
                if row["record_id"] in seen:
                    raise ValueError("Duplicate processed record ID")
                seen.add(row["record_id"])
                self.stations.append(
                    Station(
                        row["record_id"],
                        int(row["opis_truckstop_id"]),
                        row["name"],
                        row["address"],
                        row["city"],
                        row["state"],
                        price,
                        lon,
                        lat,
                        row["geocoding_source"],
                    )
                )
            if not self.stations:
                raise ValueError("No processed stations")
            self.points = [Point(*PROJECT.transform(s.longitude, s.latitude)) for s in self.stations]
            self.tree = STRtree(self.points)
        except (OSError, KeyError, ValueError, ArithmeticError) as exc:
            raise RouteError(
                "Station data unavailable or invalid. Run prepare_fuel_data.", "station_data_unavailable", 503
            ) from exc

    def initial_price(self, lon: float, lat: float) -> tuple[Station, float]:
        point = Point(*PROJECT.transform(lon, lat))
        indices = self.tree.query(point.buffer(26 * METERS_PER_MILE))
        nearby = []
        for i in indices:
            station = self.stations[int(i)]
            miles = GEOD.inv(lon, lat, station.longitude, station.latitude)[2] / METERS_PER_MILE
            if miles <= 25:
                nearby.append(
                    (
                        miles + (5 if station.geocoding_source == "city_centroid" else 0),
                        station.geocoding_source != "census",
                        station.price,
                        station.record_id,
                        station,
                        miles,
                    )
                )
        if not nearby:
            raise RouteError(
                "No dataset station within 25 miles of the origin to price initial fuel.",
                "no_initial_station",
            )
        closest = min(nearby, key=lambda item: item[:4])
        return closest[4], closest[5]

    def candidates(
        self,
        geometry: dict,
        distance_miles: float,
        corridor_miles: float,
        max_detour_miles: float,
        *,
        centroid_corridor_miles: float | None = None,
        centroid_max_detour_miles: float | None = None,
    ) -> list[Candidate]:
        coords = geometry["coordinates"]
        points = [PROJECT.transform(*point[:2]) for point in coords]
        line = LineString(points)
        if not math.isfinite(line.length) or line.length <= 0:
            raise RouteError("Unsupported degenerate route.", "unsupported_route")
        projected = [0.0]
        geodesic = [0.0]
        for a, b, pa, pb in zip(coords, coords[1:], points, points[1:], strict=False):
            projected.append(projected[-1] + math.hypot(pb[0] - pa[0], pb[1] - pa[1]))
            geodesic.append(geodesic[-1] + GEOD.inv(*a[:2], *b[:2])[2])
        if geodesic[-1] <= 0:
            raise RouteError("Unsupported degenerate route.", "unsupported_route")
        candidates = []
        city_corridor = corridor_miles if centroid_corridor_miles is None else centroid_corridor_miles
        city_detour_limit = (
            max_detour_miles if centroid_max_detour_miles is None else centroid_max_detour_miles
        )
        # Small projection distortion allowance; final corridor filtering is geodesic.
        for index in self.tree.query(
            line.buffer(max(corridor_miles, city_corridor) * METERS_PER_MILE * 1.05)
        ):
            index = int(index)
            station = self.stations[index]
            approximate = station.geocoding_source == "city_centroid"
            along = line.project(self.points[index])
            nearest = line.interpolate(along)
            lon, lat = UNPROJECT.transform(nearest.x, nearest.y)
            lateral = GEOD.inv(lon, lat, station.longitude, station.latitude)[2] / METERS_PER_MILE
            if lateral > (city_corridor if approximate else corridor_miles):
                continue
            # Centroid uncertainty is disclosed and conservatively budgeted, not hidden.
            side = lateral * 1.4 + (5.0 if approximate else 0)
            if side * 2 > (city_detour_limit if approximate else max_detour_miles):
                continue
            segment = min(bisect.bisect_right(projected, along) - 1, len(points) - 2)
            span = projected[segment + 1] - projected[segment]
            fraction = (along - projected[segment]) / span if span > 0 else 0
            progress = geodesic[segment] + fraction * (geodesic[segment + 1] - geodesic[segment])
            mile = progress / geodesic[-1] * distance_miles
            if 0 < mile < distance_miles:
                candidates.append(Candidate(station, mile, side, lateral if approximate else None))
        return sorted(candidates, key=lambda candidate: (candidate.route_mile, candidate.station.record_id))


@lru_cache(maxsize=4)
def load_index(path: str, modified_ns: int) -> StationIndex:
    return StationIndex(Path(path))


def station_index() -> StationIndex:
    try:
        path = settings.STATION_DATA_PATH
        return load_index(str(path), path.stat().st_mtime_ns)
    except OSError as exc:
        raise RouteError(
            "Processed station data missing. Run prepare_fuel_data.", "station_data_unavailable", 503
        ) from exc
