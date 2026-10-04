import csv
import hashlib
import io
import json
import math
import re
import zipfile
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

import httpx

from .addresses import classify_address, match_rejection, normalize_census_address
from .constants import US_STATES
from .routing import GEOD, coordinates

COLUMNS = ["OPIS Truckstop ID", "Truckstop Name", "Address", "City", "State", "Rack ID", "Retail Price"]
OUTPUT_COLUMNS = [
    "record_id",
    "opis_truckstop_id",
    "name",
    "address",
    "city",
    "state",
    "rack_id",
    "price",
    "longitude",
    "latitude",
    "geocoding_source",
]
GEONAMES_URL = "https://download.geonames.org/export/zip/US.zip"
CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"


def normalize(value: str) -> str:
    return " ".join(value.split())


def city_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def read_source(path: Path) -> tuple[list[dict], dict]:
    stats = Counter(raw_rows=0, non_us=0, malformed=0, exact_duplicates=0, us_rows=0)
    states: Counter = Counter()
    seen: set = set()
    records = []
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != COLUMNS:
            raise ValueError("Unexpected source CSV schema")
        for row in reader:
            stats["raw_rows"] += 1
            if None in row or any(value is None for value in row.values()):
                stats["malformed"] += 1
                continue
            row = {key: normalize(value) for key, value in row.items()}
            row["State"] = row["State"].upper()
            states[row["State"]] += 1
            if row["State"] not in US_STATES:
                stats["non_us"] += 1
                continue
            stats["us_rows"] += 1
            try:
                price = Decimal(row["Retail Price"])
                if not price.is_finite() or not 0 < price < 100:
                    raise ValueError("Invalid price")
                for key in ("OPIS Truckstop ID", "Rack ID"):
                    if int(row[key]) < 0:
                        raise ValueError("Invalid identifier")
                if any(not row[key] for key in ("Truckstop Name", "City", "Address")):
                    raise ValueError("Missing address")
            except (ValueError, InvalidOperation):
                stats["malformed"] += 1
                continue
            identity = tuple(row.values())
            if identity in seen:
                stats["exact_duplicates"] += 1
                continue
            seen.add(identity)
            records.append(
                dict(
                    zip(
                        OUTPUT_COLUMNS[:8],
                        [
                            str(len(records) + 1),
                            row["OPIS Truckstop ID"],
                            row["Truckstop Name"],
                            row["Address"],
                            row["City"],
                            row["State"],
                            row["Rack ID"],
                            str(price),
                        ],
                        strict=True,
                    )
                )
            )
    stats["us_unique_records"] = len(records)
    return records, {**stats, "state_counts": dict(sorted(states.items()))}


def load_centroids(content: bytes) -> dict[tuple[str, str], tuple[float, float]]:
    groups = defaultdict(set)
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        for row in csv.reader(io.StringIO(archive.read("US.txt").decode("utf-8")), delimiter="\t"):
            if len(row) < 12 or row[0] != "US" or row[4] not in US_STATES:
                continue
            try:
                lon, lat = coordinates([row[10], row[9]])
                groups[(city_key(row[2]), row[4])].add((lon, lat))
            except ValueError:
                continue
    result = {}
    for key, points in groups.items():
        lon = sum(p[0] for p in points) / len(points)
        lat = sum(p[1] for p in points) / len(points)
        # Large metro/postal footprints are too ambiguous for a station fallback.
        if max(GEOD.inv(lon, lat, *p)[2] for p in points) <= 16093.44:
            result[key] = (lon, lat)
    return result


def parse_census(
    text: str, records: list[dict], rejections: Counter | None = None
) -> dict[str, tuple[float, float]]:
    expected = {record["record_id"]: record for record in records}
    result = {}
    received = set()
    for row in csv.reader(io.StringIO(text)):
        if not row:
            continue
        if len(row) < 3 or row[0] not in expected or row[0] in received:
            raise ValueError("Malformed or duplicate Census response row")
        received.add(row[0])
        if row[2] != "Match":
            continue
        if len(row) < 6:
            raise ValueError("Missing Census match coordinates")
        lon, lat = coordinates(row[5].split(","))
        if not -180 <= lon <= -60 or not 18 <= lat <= 72:
            raise ValueError("Census coordinate outside US envelope")
        # Census matchedAddress ends in city, state, ZIP. Reject cross-state matches.
        address_parts = [part.strip() for part in row[4].split(",")]
        if len(address_parts) < 3 or address_parts[-2] != expected[row[0]]["state"]:
            if rejections is not None:
                rejections["different_state"] += 1
            continue
        record = expected[row[0]]
        reason = match_rejection(record["address"], record["city"], row[4])
        if reason is not None:
            if rejections is not None:
                rejections[reason] += 1
            continue
        result[row[0]] = (lon, lat)
    if received != set(expected):
        raise ValueError("Incomplete Census batch response; refusing silent data loss")
    return result


def census_batch(records: list[dict]) -> bytes:
    batch = io.StringIO(newline="")
    writer = csv.writer(batch)
    for record in records:
        writer.writerow(
            [
                record["record_id"],
                normalize_census_address(record["address"]),
                record["city"],
                record["state"],
                "",
            ]
        )
    return batch.getvalue().encode("utf-8")


def prepare(
    source: Path, output: Path, cache_dir: Path, refresh: bool = False, offline: bool = False
) -> dict:
    records, stats = read_source(source)
    if not records or len(records) > 10000:
        raise ValueError("Census batch requires between 1 and 10,000 US records")
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    cache_dir.mkdir(parents=True, exist_ok=True)
    batch = census_batch(records)
    query_hash = hashlib.sha256(batch).hexdigest()
    census_path = cache_dir / f"census-{source_hash}-{query_hash}.csv"
    # Old cached batches remain useful for offline reproduction; validate them
    # with the same stricter match checks rather than silently trusting them.
    legacy = cache_dir / f"census-{source_hash}.csv"
    if offline and not census_path.exists() and legacy.exists() and not refresh:
        census_path = legacy
    names_path = cache_dir / "geonames-US.zip"
    with httpx.Client(
        timeout=httpx.Timeout(600, connect=20), follow_redirects=True, trust_env=False
    ) as client:
        if refresh or not names_path.exists():
            if offline:
                raise ValueError("Offline mode requires cached GeoNames data")
            response = client.get(GEONAMES_URL)
            response.raise_for_status()
            load_centroids(response.content)  # Validate before replacing cache.
            names_path.write_bytes(response.content)
        if refresh or not census_path.exists():
            if offline:
                raise ValueError("Offline mode requires a cached Census batch response")
            response = client.post(
                CENSUS_URL,
                data={"benchmark": "Public_AR_Current"},
                files={"addressFile": ("addresses.csv", batch, "text/csv")},
            )
            response.raise_for_status()
            parse_census(response.text, records)
            census_path.write_text(response.text, encoding="utf-8", newline="")
    rejections = Counter()
    census_text = census_path.read_text(encoding="utf-8")
    matches = parse_census(census_text, records, rejections)
    centroids = load_centroids(names_path.read_bytes())
    prepared = []
    excluded = []
    for record in records:
        point = matches.get(record["record_id"])
        quality = "census"
        if point is None:
            point = centroids.get((city_key(record["city"]), record["state"]))
            quality = "city_centroid"
        if point is None:
            excluded.append({**record, "geocoding_source": "unmatched"})
            continue
        if not all(math.isfinite(value) for value in point):
            raise ValueError("Invalid prepared coordinates")
        prepared.append(
            {
                **record,
                "longitude": f"{point[0]:.7f}",
                "latitude": f"{point[1]:.7f}",
                "geocoding_source": quality,
            }
        )
    stats.update(
        census=len(matches),
        city_centroid=sum(r["geocoding_source"] == "city_centroid" for r in prepared),
        unmatched=len(excluded),
        located=len(prepared),
        located_percent=round(100 * len(prepared) / len(records), 2),
        source_sha256=source_hash,
        geonames_sha256=hashlib.sha256(names_path.read_bytes()).hexdigest(),
        census_response_sha256=hashlib.sha256(census_path.read_bytes()).hexdigest(),
        census_benchmark="Public_AR_Current",
        centroid_source=GEONAMES_URL,
        census_query_sha256=query_hash if census_path != legacy else None,
        census_query_normalization="normalized_v1" if census_path != legacy else "legacy_cached",
        census_cache_file=census_path.name,
        census_rejected_matches=dict(sorted(rejections.items())),
        census_response_status_counts=dict(
            Counter(row[2] for row in csv.reader(io.StringIO(census_text)) if row)
        ),
        address_pattern_counts=dict(sorted(Counter(classify_address(r["address"]) for r in records).items())),
        normalized_address_count=sum(normalize_census_address(r["address"]) != r["address"] for r in records),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(prepared)
    temporary.replace(output)
    with output.with_name("fuel_stations_unmatched.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(excluded)
    output.with_name("preprocessing_stats.json").write_text(
        json.dumps(stats, indent=2) + "\n", encoding="utf-8"
    )
    return stats
