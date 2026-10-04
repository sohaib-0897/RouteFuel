import csv
import io
import zipfile
from pathlib import Path

import pytest

from routes.preprocessing import COLUMNS, city_key, load_centroids, parse_census, prepare, read_source


def write_source(path: Path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        w.writerows(rows)


ROW = ["1", "Test Stop", "100 Main Street", "Dallas", "TX", "1", "3.12345678"]


def test_filter_normalize_exact_duplicates_keep_variants(tmp_path):
    path = tmp_path / "source.csv"
    rows = [
        ROW,
        ROW,
        [*ROW[:1], "Other Name", *ROW[2:]],
        [*ROW[:4], "ON", *ROW[5:]],
        [*ROW[:-1], "nan"],
        [*ROW[:-1], "oops"],
        ["2", "  Other   Stop  ", " 100 Main ", " Dallas ", " tx ", "1", "3.5"],
    ]
    write_source(path, rows)
    records, stats = read_source(path)
    assert stats["raw_rows"] == 7
    assert stats["non_us"] == 1
    assert stats["malformed"] == 2
    assert stats["exact_duplicates"] == 1
    assert len(records) == 3
    assert records[-1]["name"] == "Other Stop"
    assert records[0]["price"] == "3.12345678"
    assert records[0]["opis_truckstop_id"] == records[1]["opis_truckstop_id"]


@pytest.mark.parametrize("row", [[*ROW[:-1], "-1"], [*ROW[:-1], "0"], [*ROW, "extra"], ROW[:-1]])
def test_malformed_rows(tmp_path, row):
    path = tmp_path / "source.csv"
    write_source(path, [row])
    records, stats = read_source(path)
    assert not records
    assert stats["malformed"] == 1


def test_schema_validation(tmp_path):
    path = tmp_path / "source.csv"
    path.write_text("wrong,columns\n1,2\n")
    with pytest.raises(ValueError, match="schema"):
        read_source(path)


def census_response(records, matched=True):
    stream = io.StringIO()
    writer = csv.writer(stream)
    for record in records:
        writer.writerow(
            [
                record["record_id"],
                "input",
                "Match" if matched else "No_Match",
                "Exact",
                "100 MAIN ST, DALLAS, TX, 75001",
                "-96.797,32.7767",
                "123",
                "L",
            ]
        )
    return stream.getvalue()


def test_census_coordinate_order_and_state(tmp_path):
    path = tmp_path / "source.csv"
    write_source(path, [ROW])
    records, _ = read_source(path)
    assert parse_census(census_response(records), records) == {"1": (-96.797, 32.7767)}
    assert parse_census(census_response(records).replace(", TX,", ", OK,"), records) == {}
    assert parse_census(census_response(records, False), records) == {}
    with pytest.raises(ValueError):
        parse_census("", records)
    with pytest.raises(ValueError):
        parse_census(census_response(records) * 2, records)


def zip_centroids():
    content = io.BytesIO()
    with zipfile.ZipFile(content, "w") as archive:
        archive.writestr("US.txt", "US\t75001\tDallas\tTexas\tTX\tDallas\t001\t\t\t32.7767\t-96.7970\t4\n")
    return content.getvalue()


def test_offline_city_centroids():
    assert load_centroids(zip_centroids()) == {(city_key("Dallas"), "TX"): (-96.797, 32.7767)}


def test_full_prepare_idempotent_offline_and_no_raw_mutation(tmp_path):
    import hashlib

    source, output, cached = tmp_path / "raw.csv", tmp_path / "data/stations.csv", tmp_path / "cached"
    write_source(source, [ROW, ["2", "Unknown", "Exit 42", "No Such City", "TX", "1", "4"]])
    original = source.read_bytes()
    records, _ = read_source(source)
    cached.mkdir()
    (cached / "geonames-US.zip").write_bytes(zip_centroids())
    (cached / f"census-{hashlib.sha256(original).hexdigest()}.csv").write_text(
        census_response(records, False)
    )
    first = prepare(source, output, cached, offline=True)
    data = output.read_bytes()
    second = prepare(source, output, cached, offline=True)
    assert first == second
    assert data == output.read_bytes()
    assert original == source.read_bytes()
    assert first["city_centroid"] == 1
    assert first["unmatched"] == 1
    assert first["located_percent"] == 50
    assert output.with_name("fuel_stations_unmatched.csv").exists()


def test_offline_without_cache_fails(tmp_path):
    source = tmp_path / "raw.csv"
    write_source(source, [ROW])
    with pytest.raises(ValueError, match="cached GeoNames"):
        prepare(source, tmp_path / "out.csv", tmp_path / "cache", offline=True)


def test_remote_prepare_uses_two_batch_level_calls(tmp_path):
    from unittest.mock import patch

    import httpx

    source = tmp_path / "raw.csv"
    write_source(source, [ROW])
    records, _ = read_source(source)
    requests = []
    real_client = httpx.Client

    def handler(request):
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, content=zip_centroids())
        assert b"Public_AR_Current" in request.content
        assert b"100 MAIN ST" in request.content
        return httpx.Response(200, text=census_response(records))

    def factory(**kwargs):
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    with patch("routes.preprocessing.httpx.Client", side_effect=factory):
        stats = prepare(source, tmp_path / "out.csv", tmp_path / "cache")
        assert stats["census"] == 1
        assert stats["city_centroid"] == 0
        assert len(requests) == 2
        prepare(source, tmp_path / "out.csv", tmp_path / "cache")
        assert len(requests) == 2
