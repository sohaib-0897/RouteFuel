import csv
import hashlib
import json
from pathlib import Path

from routes.constants import US_STATES


def test_committed_dataset_matches_original_and_statistics():
    root = Path(__file__).resolve().parent.parent
    stats = json.loads((root / "data/preprocessing_stats.json").read_text())
    original = root / "fuel-prices-for-be-assessment.csv"
    assert hashlib.sha256(original.read_bytes()).hexdigest() == stats["source_sha256"]
    with original.open(newline="", encoding="utf-8-sig") as stream:
        assert sum(1 for _ in csv.DictReader(stream)) == stats["raw_rows"]
    with (root / "data/fuel_stations_processed.csv").open(newline="", encoding="utf-8") as stream:
        records = list(csv.DictReader(stream))
    assert len(records) == stats["located"] == stats["census"] + stats["city_centroid"]
    assert all(row["state"] in US_STATES for row in records)
    assert sum(row["geocoding_source"] == "census" for row in records) == stats["census"]
    assert len({row["record_id"] for row in records}) == len(records)
    with (root / "data/fuel_stations_unmatched.csv").open(newline="", encoding="utf-8") as stream:
        excluded = list(csv.DictReader(stream))
    assert len(excluded) == stats["unmatched"]
    assert len(records) + len(excluded) == stats["us_unique_records"]
