import os
import uuid
from pathlib import Path

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-only")
os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from routes.stations import StationIndex, load_index

# Windows restricted tokens cannot reopen pytest's owner-only (0700) temp
# directories. Use normal inherited workspace permissions on this platform.
if os.name == "nt":

    @pytest.fixture
    def tmp_path():
        path = Path(__file__).resolve().parent.parent / ".cache" / "testtmp" / uuid.uuid4().hex
        path.mkdir(parents=True)
        return path


@pytest.fixture(autouse=True)
def isolated_settings(settings):
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    settings.ORS_API_KEY = "mock-key"
    settings.SECURE_SSL_REDIRECT = False
    settings.ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
    settings.STATION_DATA_PATH = Path(__file__).parent / "fixtures/stations.csv"
    cache.clear()
    load_index.cache_clear()
    yield
    cache.clear()
    load_index.cache_clear()


@pytest.fixture
def index(settings):
    return StationIndex(settings.STATION_DATA_PATH)


@pytest.fixture
def api():
    return APIClient()
