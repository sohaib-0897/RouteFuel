from dataclasses import replace
from pathlib import Path

import pytest

from routes.errors import RouteError
from routes.stations import StationIndex, station_index


def test_progress_and_corridor(index):
    coords = [[s.longitude, s.latitude] for s in index.stations]
    candidates = index.candidates({"coordinates": coords}, 1400, 15, 20)
    assert len(candidates) == 3
    assert all(c.side_miles < 0.001 for c in candidates)
    assert [c.route_mile for c in candidates] == sorted(c.route_mile for c in candidates)
    assert 0 < candidates[0].route_mile < candidates[-1].route_mile < 1400


def test_far_cheap_station_excluded(index):
    # Dallas -> Midland: Phoenix and LA cannot enter this corridor.
    line = {"coordinates": [[-96.7970, 32.7767], [-102.0779, 31.9973]]}
    assert all(c.station.state == "TX" for c in index.candidates(line, 350, 15, 20))
    assert index.candidates(line, 350, 15, -1) == []


def test_no_initial_corridor_station(index):
    with pytest.raises(RouteError, match="No dataset station"):
        index.initial_price(-70, 44)


def test_initial_price_reference_distance(index):
    station, miles = index.initial_price(-96.797, 32.7767)
    assert station.opis_truckstop_id == 101
    assert miles == 0


def test_missing_processed_data(settings):
    settings.STATION_DATA_PATH = Path("missing-file.csv")
    with pytest.raises(RouteError) as exc:
        station_index()
    assert exc.value.status_code == 503


def test_invalid_processed_data_rejected(tmp_path, settings):
    path = tmp_path / "bad.csv"
    path.write_text(settings.STATION_DATA_PATH.read_text().replace(",TX,", ",ON,"))
    with pytest.raises(RouteError):
        StationIndex(path)


def test_index_loaded_once(settings):
    assert station_index() is station_index()


def test_centroid_uncertainty_adds_access_budget(index):
    index.stations[1] = replace(index.stations[1], geocoding_source="city_centroid")
    coords = [[s.longitude, s.latitude] for s in index.stations]
    selected = index.candidates({"coordinates": coords}, 1400, 15, 20)
    centroid = next(c for c in selected if c.station.opis_truckstop_id == 102)
    assert centroid.side_miles == pytest.approx(5)
    assert all(
        c.station.opis_truckstop_id != 102 for c in index.candidates({"coordinates": coords}, 1400, 15, 9)
    )
